import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView
from django.views.generic.edit import FormView

from orchestration.llm import LLMError

from .choices import ConversationStatus, ConversationTurnState
from .forms import ChatMessageForm
from .models import Conversation
from .services import (
    close_conversation,
    create_assistant_message,
    create_user_message,
    generate_assistant_reply,
    get_or_create_active_conversation,
    maybe_refresh_conversation_summary,
)

logger = logging.getLogger("seher.conversations")


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def is_ajax_request(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def form_errors_as_dict(form):
    return {field: [str(error) for error in errors] for field, errors in form.errors.items()}


def submit_message_to_conversation(*, request, conversation, content):
    if conversation.status != ConversationStatus.ACTIVE:
        raise ValueError("This conversation is closed.")

    if conversation.turn_state != ConversationTurnState.IDLE:
        raise ValueError("Seher is still responding to your last message.")

    content = (content or "").strip()
    if not content:
        raise ValueError("Message cannot be empty.")

    ip_address = get_client_ip(request)

    with transaction.atomic():
        conversation = Conversation.objects.select_for_update().get(pk=conversation.pk)

        if conversation.status != ConversationStatus.ACTIVE:
            raise ValueError("This conversation is closed.")

        if conversation.turn_state != ConversationTurnState.IDLE:
            raise ValueError("Seher is still responding to your last message.")

        conversation.turn_state = ConversationTurnState.WAITING_FOR_ASSISTANT
        conversation.save(
            update_fields=[
                "turn_state",
                "updated_at",
            ]
        )

        user_message = create_user_message(
            conversation=conversation,
            content=content,
            ip_address=ip_address,
        )

    try:
        assistant_text = generate_assistant_reply(
            conversation=conversation,
            message=user_message,
        )
    except Exception:
        logger.exception(
            "Assistant response generation failed | conversation=%s message=%s",
            conversation.pk,
            user_message.pk,
        )

        Conversation.objects.filter(
            pk=conversation.pk,
        ).update(
            turn_state=ConversationTurnState.IDLE,
            updated_at=timezone.now(),
        )

        raise

    with transaction.atomic():
        conversation = Conversation.objects.select_for_update().get(pk=conversation.pk)

        create_assistant_message(
            conversation=conversation,
            content=assistant_text,
        )

        conversation.last_message_at = timezone.now()
        conversation.turn_state = ConversationTurnState.IDLE
        conversation.save(
            update_fields=[
                "last_message_at",
                "turn_state",
                "updated_at",
            ]
        )

    try:
        maybe_refresh_conversation_summary(conversation)
    except Exception:
        logger.exception(
            "Conversation summary refresh failed | conversation=%s",
            conversation.pk,
        )

    return assistant_text


class ConversationHubView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        conversation = get_or_create_active_conversation(request.user)
        return redirect(
            "conversations:detail",
            pk=conversation.pk,
        )


class ConversationDetailView(LoginRequiredMixin, DetailView):
    model = Conversation
    template_name = "conversations/detail.html"
    context_object_name = "conversation"

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user).prefetch_related("messages")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = ChatMessageForm()
        context["can_send_message"] = (
            self.object.status == ConversationStatus.ACTIVE
            and self.object.turn_state == ConversationTurnState.IDLE
        )
        context["is_waiting"] = (
            self.object.turn_state == ConversationTurnState.WAITING_FOR_ASSISTANT
        )
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = ChatMessageForm(request.POST)

        if not form.is_valid():
            return self.form_invalid(form)

        try:
            submit_message_to_conversation(
                request=request,
                conversation=self.object,
                content=form.cleaned_data["content"],
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        except Exception:
            form.add_error(
                None,
                "Seher could not respond right now. Please try again.",
            )

            self.object.refresh_from_db()

            return self.form_invalid(form)

        return redirect(
            "conversations:detail",
            pk=self.object.pk,
        )

    def form_invalid(self, form):
        conversation = self.get_object()
        messages = conversation.messages.all()

        return self.render_to_response(
            self.get_context_data(
                form=form,
                conversation=conversation,
                messages=messages,
            )
        )


class ConversationSendMessageView(LoginRequiredMixin, FormView):
    form_class = ChatMessageForm
    http_method_names = ["post"]

    def dispatch(self, request, *args, **kwargs):
        self.conversation = Conversation.objects.filter(
            pk=kwargs["pk"],
            user=request.user,
        ).first()

        if not self.conversation:
            raise Http404("Conversation not found.")

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            assistant_text = submit_message_to_conversation(
                request=self.request,
                conversation=self.conversation,
                content=form.cleaned_data["content"],
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        except LLMError:
            form.add_error(
                None, "Seher's response service is temporarily unavailable. Please try again later."
            )
            self.conversation.refresh_from_db()
            return self.form_invalid(form, status=503)
        except Exception:
            form.add_error(
                None,
                "Seher could not respond right now. Please try again.",
            )

            self.conversation.refresh_from_db()

            return self.form_invalid(form)

        if is_ajax_request(self.request):
            assistant_message = (
                self.conversation.messages.filter(role="assistant")
                .order_by("-sequence_number")
                .first()
            )

            if not assistant_message:
                return JsonResponse(
                    {
                        "success": False,
                        "error": ("Seher responded, but the response could not " "be saved."),
                    },
                    status=500,
                )

            return JsonResponse(
                {
                    "success": True,
                    "assistant_message": {
                        "content": assistant_message.content,
                        "created_at": timezone.localtime(assistant_message.created_at).isoformat(),
                    },
                }
            )

        return redirect(
            "conversations:detail",
            pk=self.conversation.pk,
        )

    def form_invalid(self, form, *, status=400):
        conversation = self.conversation
        messages = conversation.messages.all()

        if is_ajax_request(self.request):
            return JsonResponse(
                {
                    "success": False,
                    "errors": form_errors_as_dict(form),
                    "error": (
                        "Seher's response service is temporarily unavailable. Please try again later."
                        if status == 503
                        else "Please correct the message and try again."
                    ),
                },
                status=status,
            )

        return self.render_to_response(
            self.get_context_data(
                form=form,
                conversation=conversation,
                messages=messages,
            ),
            status=status,
        )


class ConversationCloseView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        conversation = Conversation.objects.filter(
            pk=kwargs["pk"],
            user=request.user,
        ).first()

        if not conversation:
            raise Http404("Conversation not found.")

        close_conversation(conversation)

        return redirect("conversations:history")


class ConversationHistoryView(LoginRequiredMixin, ListView):
    model = Conversation
    template_name = "conversations/history.html"
    context_object_name = "conversations"

    def get_queryset(self):
        return Conversation.objects.filter(
            user=self.request.user,
            status=ConversationStatus.CLOSED,
        ).order_by("-closed_at", "-created_at")

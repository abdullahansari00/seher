import logging
from django.db.models import Max
from django.utils import timezone

from .choices import ConversationStatus, MessageRole, ConversationTurnState
from .models import Conversation, Message
from orchestration.execution import (
    complete_agent_run,
    fail_agent_run,
    start_agent_run,
)
from orchestration.graph import seher_graph
from orchestration.services import update_conversation_summary

logger = logging.getLogger("seher.conversations")


def get_or_create_active_conversation(user):
    conversation = (
        Conversation.objects.filter(
            user=user,
            status=ConversationStatus.ACTIVE,
        )
        .order_by("-created_at")
        .first()
    )

    if conversation:
        return conversation

    return Conversation.objects.create(
        user=user,
        status=ConversationStatus.ACTIVE,
        turn_state=ConversationTurnState.IDLE,
    )


def get_next_sequence_number(conversation):
    last_sequence = conversation.messages.aggregate(max_seq=Max("sequence_number"))["max_seq"] or 0
    return last_sequence + 1


def create_user_message(
    conversation,
    content,
    ip_address=None,
    metadata=None,
):
    metadata = metadata or {}

    return Message.objects.create(
        conversation=conversation,
        role=MessageRole.USER,
        sequence_number=get_next_sequence_number(conversation),
        content=content,
        ip_address=ip_address,
        metadata=metadata,
    )


def create_assistant_message(
    conversation,
    content,
    metadata=None,
):
    metadata = metadata or {}

    return Message.objects.create(
        conversation=conversation,
        role=MessageRole.ASSISTANT,
        sequence_number=get_next_sequence_number(conversation),
        content=content,
        metadata=metadata,
    )


def build_conversation_context(conversation, *, limit=8) -> str:
    messages = list(
        conversation.messages.order_by("-created_at").only(
            "role",
            "content",
        )[:limit]
    )
    messages.reverse()

    sections = []

    if conversation.summary.strip():
        sections.append("Conversation summary:\n" f"{conversation.summary.strip()}")

    if messages:
        lines = [f"{message.role.upper()}: {message.content}" for message in messages]

        sections.append("Recent messages:\n" + "\n".join(lines))

    if not sections:
        return "None"

    return "\n\n".join(sections)


def maybe_refresh_conversation_summary(conversation, *, batch_size=4):
    pending_user_messages = list(
        conversation.messages.filter(
            role=MessageRole.USER,
            sequence_number__gt=conversation.last_summarized_user_message_sequence_number,
        ).order_by("sequence_number")[:batch_size]
    )

    if len(pending_user_messages) < batch_size:
        return False

    batch_text = "\n".join(f"USER: {message.content}" for message in pending_user_messages)

    updated_summary = update_conversation_summary(
        existing_summary=conversation.summary,
        new_user_messages_text=batch_text,
    )

    if updated_summary.strip():
        conversation.summary = updated_summary.strip()

    conversation.last_summarized_user_message_sequence_number = pending_user_messages[
        -1
    ].sequence_number

    conversation.save(
        update_fields=[
            "summary",
            "last_summarized_user_message_sequence_number",
            "updated_at",
        ]
    )

    return True


def generate_assistant_reply(*, conversation, message):
    agent_run = start_agent_run(
        conversation=conversation,
        message=message,
    )
    logger.info(
        "Started assistant response generation | " "conversation=%s message=%s run=%s",
        conversation.pk,
        message.pk,
        agent_run.pk,
    )

    try:
        conversation_context = build_conversation_context(
            conversation,
            limit=8,
        )

        result = seher_graph.invoke(
            {
                "conversation_id": conversation.id,
                "user_message_id": message.id,
                "user_message": message.content,
                "agent_run_id": agent_run.id,
                "conversation_mode": conversation.mode,
                "evaluation_mode": False,
                "conversation_context": conversation_context,
                "safety_assessment": {},
                "safety_route": "normal",
                "workflow_route": "support",
                "retrieved_context": [],
                "response": "",
                "end_node": "",
            }
        )

        response = result["response"]

        complete_agent_run(
            agent_run,
            result=result,
        )

        logger.info(
            "Completed assistant response generation | " "conversation=%s message=%s run=%s",
            conversation.pk,
            message.pk,
            agent_run.pk,
        )

        return response

    except Exception as exc:
        logger.exception(
            "Assistant response generation failed | " "conversation=%s message=%s run=%s",
            conversation.pk,
            message.pk,
            agent_run.pk,
        )

        fail_agent_run(
            agent_run,
            exc,
        )
        raise


def close_conversation(conversation):
    conversation.status = ConversationStatus.CLOSED
    conversation.turn_state = ConversationTurnState.IDLE
    conversation.closed_at = timezone.now()
    conversation.save(
        update_fields=[
            "status",
            "turn_state",
            "closed_at",
            "updated_at",
        ]
    )

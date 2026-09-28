from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from conversations.choices import (
    ConversationStatus,
    ConversationTurnState,
    MessageRole,
)
from conversations.models import Conversation

User = get_user_model()


class ConversationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="view_test_user",
            email="view_test@example.com",
            password="test-password",
        )
        self.client.login(
            username="view_test_user",
            password="test-password",
        )

    def test_post_message_creates_user_message_and_assistant_message(self):
        conversation = Conversation.objects.create(
            user=self.user,
            status=ConversationStatus.ACTIVE,
            turn_state=ConversationTurnState.IDLE,
        )

        with patch(
            "conversations.views.generate_assistant_reply",
            return_value="I hear you. That sounds really hard.",
        ) as mock_generate_reply:
            response = self.client.post(
                reverse("conversations:detail", args=[conversation.pk]),
                data={
                    "content": "I had a rough day.",
                },
            )

        self.assertEqual(response.status_code, 302)

        conversation.refresh_from_db()

        self.assertEqual(
            conversation.turn_state,
            ConversationTurnState.IDLE,
        )

        self.assertEqual(
            conversation.messages.count(),
            2,
        )

        self.assertEqual(
            conversation.messages.first().role,
            MessageRole.USER,
        )

        self.assertEqual(
            conversation.messages.last().role,
            MessageRole.ASSISTANT,
        )

        mock_generate_reply.assert_called_once()

    def test_cannot_post_when_conversation_is_closed(self):
        conversation = Conversation.objects.create(
            user=self.user,
            status=ConversationStatus.CLOSED,
            turn_state=ConversationTurnState.IDLE,
        )

        response = self.client.post(
            reverse("conversations:detail", args=[conversation.pk]),
            data={
                "content": "Can I still send this?",
            },
        )

        self.assertEqual(response.status_code, 200)

        conversation.refresh_from_db()

        self.assertEqual(conversation.messages.count(), 0)
        self.assertEqual(
            conversation.turn_state,
            ConversationTurnState.IDLE,
        )

        self.assertContains(
            response,
            "This conversation is closed.",
        )

    def test_turn_state_can_be_set_to_waiting_during_processing(self):
        conversation = Conversation.objects.create(
            user=self.user,
            status=ConversationStatus.ACTIVE,
            turn_state=ConversationTurnState.IDLE,
        )

        with patch(
            "conversations.views.generate_assistant_reply",
            return_value="Sure, I’m here.",
        ):
            self.client.post(
                reverse("conversations:detail", args=[conversation.pk]),
                data={
                    "content": "Hello",
                },
            )

        conversation.refresh_from_db()

        self.assertEqual(
            conversation.turn_state,
            ConversationTurnState.IDLE,
        )

    @patch(
        "conversations.views.generate_assistant_reply",
        side_effect=RuntimeError("LLM unavailable"),
    )
    def test_generation_failure_resets_conversation_turn_state(
        self,
        mock_generate_reply,
    ):
        conversation = Conversation.objects.create(
            user=self.user,
            status=ConversationStatus.ACTIVE,
            turn_state=ConversationTurnState.IDLE,
        )

        response = self.client.post(
            reverse(
                "conversations:detail",
                args=[conversation.pk],
            ),
            data={
                "content": "I need someone to talk to.",
            },
        )

        self.assertEqual(response.status_code, 200)

        conversation.refresh_from_db()

        self.assertEqual(
            conversation.turn_state,
            ConversationTurnState.IDLE,
        )

        self.assertEqual(
            conversation.messages.count(),
            1,
        )

        self.assertEqual(
            conversation.messages.first().role,
            MessageRole.USER,
        )

        mock_generate_reply.assert_called_once()

    @patch(
        "conversations.views.maybe_refresh_conversation_summary",
        side_effect=RuntimeError("Summary service unavailable"),
    )
    @patch(
        "conversations.views.generate_assistant_reply",
        return_value="That sounds really difficult.",
    )
    def test_summary_failure_does_not_fail_successful_message(
        self,
        mock_generate_reply,
        mock_refresh_summary,
    ):
        conversation = Conversation.objects.create(
            user=self.user,
            status=ConversationStatus.ACTIVE,
            turn_state=ConversationTurnState.IDLE,
        )

        response = self.client.post(
            reverse(
                "conversations:detail",
                args=[conversation.pk],
            ),
            data={
                "content": "Today was really difficult.",
            },
        )

        self.assertEqual(response.status_code, 302)

        conversation.refresh_from_db()

        self.assertEqual(
            conversation.turn_state,
            ConversationTurnState.IDLE,
        )

        self.assertEqual(
            conversation.messages.count(),
            2,
        )

        self.assertEqual(
            conversation.messages.last().content,
            "That sounds really difficult.",
        )

        mock_generate_reply.assert_called_once()
        mock_refresh_summary.assert_called_once()

    @patch(
        "conversations.views.generate_assistant_reply",
        return_value="I'm here with you.",
    )
    def test_ajax_message_returns_json_without_redirect(
        self,
        mock_generate_reply,
    ):
        conversation = Conversation.objects.create(
            user=self.user,
            status=ConversationStatus.ACTIVE,
            turn_state=ConversationTurnState.IDLE,
        )

        response = self.client.post(
            reverse(
                "conversations:send",
                args=[conversation.pk],
            ),
            data={
                "content": "I need to talk.",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertTrue(data["success"])
        self.assertEqual(
            data["assistant_message"]["content"],
            "I'm here with you.",
        )

        conversation.refresh_from_db()

        self.assertEqual(
            conversation.messages.count(),
            2,
        )

        mock_generate_reply.assert_called_once()

    def test_model_failure_returns_service_unavailable_and_releases_turn(self):
        from orchestration.llm import LLMError

        conversation = Conversation.objects.create(user=self.user)
        with patch(
            "conversations.views.generate_assistant_reply", side_effect=LLMError("upstream failure")
        ):
            response = self.client.post(
                reverse("conversations:send", args=[conversation.pk]),
                data={"content": "I had a difficult day."},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn("temporarily unavailable", response.json()["error"])
        conversation.refresh_from_db()
        self.assertEqual(conversation.turn_state, ConversationTurnState.IDLE)
        self.assertEqual(conversation.messages.filter(role=MessageRole.USER).count(), 1)
        self.assertFalse(conversation.messages.filter(role=MessageRole.ASSISTANT).exists())

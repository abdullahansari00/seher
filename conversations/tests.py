from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from .choices import (
    ConversationMode,
    ConversationStatus,
    ConversationTurnState,
    MessageRole,
)
from .models import Conversation
from .services import (
    build_conversation_context,
    create_assistant_message,
    create_user_message,
    generate_assistant_reply,
    get_or_create_active_conversation,
    maybe_refresh_conversation_summary,
)

User = get_user_model()


class ConversationServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="conversation_test_user",
            email="conversation_test@example.com",
            password="test-password",
        )

    def test_get_or_create_active_conversation_reuses_existing_active_conversation(self):
        conversation1 = get_or_create_active_conversation(self.user)
        conversation2 = get_or_create_active_conversation(self.user)

        self.assertEqual(conversation1.pk, conversation2.pk)

        self.assertEqual(
            Conversation.objects.filter(
                user=self.user,
                status=ConversationStatus.ACTIVE,
            ).count(),
            1,
        )

    def test_closed_conversation_allows_new_active_conversation(self):
        first_conversation = get_or_create_active_conversation(self.user)

        first_conversation.status = ConversationStatus.CLOSED
        first_conversation.turn_state = ConversationTurnState.IDLE
        first_conversation.save(
            update_fields=[
                "status",
                "turn_state",
                "updated_at",
            ]
        )

        second_conversation = get_or_create_active_conversation(self.user)

        self.assertNotEqual(
            first_conversation.pk,
            second_conversation.pk,
        )

        self.assertEqual(
            Conversation.objects.filter(
                user=self.user,
                status=ConversationStatus.ACTIVE,
            ).count(),
            1,
        )

        self.assertEqual(
            Conversation.objects.filter(
                user=self.user,
                status=ConversationStatus.CLOSED,
            ).count(),
            1,
        )

    def test_user_message_stores_ip_address(self):
        conversation = get_or_create_active_conversation(self.user)

        message = create_user_message(
            conversation=conversation,
            content="I had a difficult day.",
            ip_address="192.168.1.10",
        )

        self.assertEqual(message.role, MessageRole.USER)
        self.assertEqual(message.ip_address, "192.168.1.10")

    def test_message_sequence_numbers_are_unique_and_increment(self):
        conversation = get_or_create_active_conversation(self.user)

        user_message = create_user_message(
            conversation=conversation,
            content="Hello",
        )

        assistant_message = create_assistant_message(
            conversation=conversation,
            content="Hi.",
        )

        second_user_message = create_user_message(
            conversation=conversation,
            content="How are you?",
        )

        self.assertEqual(user_message.sequence_number, 1)
        self.assertEqual(assistant_message.sequence_number, 2)
        self.assertEqual(second_user_message.sequence_number, 3)

        self.assertEqual(
            conversation.messages.count(),
            3,
        )

    def test_build_conversation_context_includes_summary_and_only_last_8_messages(self):
        conversation = get_or_create_active_conversation(self.user)

        conversation.summary = "The user is dealing with ongoing work stress."
        conversation.save(
            update_fields=[
                "summary",
                "updated_at",
            ]
        )

        for index in range(1, 6):
            create_user_message(
                conversation=conversation,
                content=f"user message {index}",
            )
            create_assistant_message(
                conversation=conversation,
                content=f"assistant message {index}",
            )

        context = build_conversation_context(
            conversation,
            limit=8,
        )

        self.assertIn(
            "Conversation summary:\n" "The user is dealing with ongoing work stress.",
            context,
        )

        self.assertNotIn("user message 1", context)
        self.assertNotIn("assistant message 1", context)

        for index in range(2, 6):
            self.assertIn(
                f"user message {index}",
                context,
            )
            self.assertIn(
                f"assistant message {index}",
                context,
            )

    @patch("conversations.services.update_conversation_summary")
    def test_summary_is_not_refreshed_before_4_user_messages(
        self,
        mock_update_summary,
    ):
        conversation = get_or_create_active_conversation(self.user)

        for index in range(1, 4):
            create_user_message(
                conversation=conversation,
                content=f"user message {index}",
            )

        refreshed = maybe_refresh_conversation_summary(conversation)

        self.assertFalse(refreshed)
        mock_update_summary.assert_not_called()

        conversation.refresh_from_db()

        self.assertEqual(
            conversation.summary,
            "",
        )

        self.assertEqual(
            conversation.last_summarized_user_message_sequence_number,
            0,
        )

    @patch("conversations.services.update_conversation_summary")
    def test_summary_refreshes_after_4_user_messages_and_uses_only_user_messages(
        self,
        mock_update_summary,
    ):
        mock_update_summary.return_value = "The user has been experiencing work-related stress."

        conversation = get_or_create_active_conversation(self.user)

        for index in range(1, 5):
            create_user_message(
                conversation=conversation,
                content=f"user message {index}",
            )
            create_assistant_message(
                conversation=conversation,
                content=f"assistant message {index}",
            )

        refreshed = maybe_refresh_conversation_summary(conversation)

        self.assertTrue(refreshed)

        mock_update_summary.assert_called_once_with(
            existing_summary="",
            new_user_messages_text=(
                "USER: user message 1\n"
                "USER: user message 2\n"
                "USER: user message 3\n"
                "USER: user message 4"
            ),
        )

        conversation.refresh_from_db()

        self.assertEqual(
            conversation.summary,
            "The user has been experiencing work-related stress.",
        )

        # User messages are sequences 1, 3, 5, 7.
        self.assertEqual(
            conversation.last_summarized_user_message_sequence_number,
            7,
        )

    @patch("conversations.services.update_conversation_summary")
    def test_generate_assistant_reply_passes_summary_and_recent_context_to_graph(
        self,
        mock_update_summary,
    ):
        mock_update_summary.return_value = "Updated conversation summary."

        conversation = get_or_create_active_conversation(self.user)

        conversation.summary = "The user has been dealing with work stress."
        conversation.save(
            update_fields=[
                "summary",
                "updated_at",
            ]
        )

        create_user_message(
            conversation=conversation,
            content="Earlier message",
        )

        message = create_user_message(
            conversation=conversation,
            content="I feel exhausted today.",
        )

        fake_agent_run = Mock()
        fake_agent_run.id = 123

        graph_result = {
            "response": "That sounds exhausting.",
        }

        with (
            patch(
                "conversations.services.start_agent_run",
                return_value=fake_agent_run,
            ),
            patch(
                "conversations.services.complete_agent_run",
            ) as mock_complete_agent_run,
            patch(
                "conversations.services.fail_agent_run",
            ) as mock_fail_agent_run,
            patch(
                "conversations.services.seher_graph.invoke",
                return_value=graph_result,
            ) as mock_graph_invoke,
        ):
            response = generate_assistant_reply(
                conversation=conversation,
                message=message,
            )

        self.assertEqual(
            response,
            "That sounds exhausting.",
        )

        state = mock_graph_invoke.call_args.args[0]

        self.assertIn(
            "The user has been dealing with work stress.",
            state["conversation_context"],
        )

        self.assertIn(
            "I feel exhausted today.",
            state["conversation_context"],
        )

        mock_complete_agent_run.assert_called_once()
        mock_fail_agent_run.assert_not_called()

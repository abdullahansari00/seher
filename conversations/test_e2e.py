from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from conversations.choices import (
    ConversationMode,
    ConversationStatus,
    ConversationTurnState,
    MessageRole,
)
from conversations.models import Conversation
from conversations.services import (
    create_assistant_message,
    create_user_message,
)
from orchestration.models import AIModelConfig, AgentConfig
from orchestration.schemas import (
    OutputSafetyDecision,
    SafetyAssessmentResult,
    SupervisorDecision,
)

User = get_user_model()


class SeherEndToEndTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="e2e_test_user",
            email="e2e_test@example.com",
            password="test-password",
        )

        self.client.login(
            username="e2e_test_user",
            password="test-password",
        )

        self.model_config = AIModelConfig.objects.create(
            name="e2e-test-model",
            provider="gemini",
            model_name="test-model",
            purpose="chat",
            temperature=0.7,
            max_output_tokens=512,
            timeout_seconds=30,
            is_default=False,
            enabled=True,
        )

        for slug, temperature in (
            ("safety", 0),
            ("supervisor", 0),
            ("support", 0.7),
            ("crisis", 0.7),
            ("output_safety", 0),
        ):
            AgentConfig.objects.create(
                slug=slug,
                name=slug.replace("_", " ").title(),
                description=f"E2E test {slug} agent.",
                system_prompt=f"You are the E2E test {slug} agent.",
                model_config=self.model_config,
                temperature=temperature,
                enabled=True,
                version=1,
            )

    def create_conversation(self):
        return Conversation.objects.create(
            user=self.user,
            status=ConversationStatus.ACTIVE,
            mode=ConversationMode.NORMAL,
            turn_state=ConversationTurnState.IDLE,
        )

    def test_support_message_flows_from_http_to_graph_and_back(self):
        conversation = self.create_conversation()

        with (
            patch("orchestration.graph.save_safety_assessment"),
            patch("orchestration.graph.save_retrieval"),
            patch("orchestration.graph.save_handoff"),
            patch("orchestration.graph.run_agent") as mock_run_agent,
        ):

            def run_agent_side_effect(
                agent_slug,
                user_message,
                conversation_context="",
                additional_context="",
            ):
                if agent_slug == "safety":
                    return SafetyAssessmentResult(
                        crisis_resolution="not_applicable",
                        risk_level="normal",
                        relevant_risk_categories=[],
                        recommended_action="allow",
                    )

                if agent_slug == "supervisor":
                    return SupervisorDecision(
                        route="support",
                    )

                if agent_slug == "support":
                    return "That sounds really difficult. I'm listening."

                if agent_slug == "output_safety":
                    return OutputSafetyDecision(
                        action="allow",
                        reason="",
                        revised_response="",
                    )

                raise AssertionError(f"Unexpected agent: {agent_slug}")

            mock_run_agent.side_effect = run_agent_side_effect

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
            conversation.mode,
            ConversationMode.NORMAL,
        )

        messages = list(conversation.messages.order_by("sequence_number"))

        self.assertEqual(len(messages), 2)

        self.assertEqual(
            messages[0].role,
            MessageRole.USER,
        )

        self.assertEqual(
            messages[0].content,
            "Today was really difficult.",
        )

        self.assertEqual(
            messages[1].role,
            MessageRole.ASSISTANT,
        )

        self.assertEqual(
            messages[1].content,
            "That sounds really difficult. I'm listening.",
        )

        called_agents = [call.kwargs["agent_slug"] for call in mock_run_agent.call_args_list]

        self.assertEqual(
            called_agents,
            [
                "safety",
                "supervisor",
                "support",
                "output_safety",
            ],
        )

    def test_crisis_message_bypasses_supervisor_and_reaches_crisis_agent(self):
        conversation = self.create_conversation()

        with (
            patch("orchestration.graph.save_safety_assessment"),
            patch("orchestration.graph.save_retrieval"),
            patch("orchestration.graph.save_handoff") as mock_save_handoff,
            patch(
                "orchestration.graph.get_crisis_resources",
                return_value={
                    "country": "TEST",
                    "resources": [
                        {
                            "id": "test_emergency",
                            "name": "Test Emergency Service",
                            "purpose": "Immediate danger",
                            "phone": "000",
                        }
                    ],
                },
            ),
            patch("orchestration.graph.run_agent") as mock_run_agent,
        ):

            def run_agent_side_effect(
                agent_slug,
                user_message,
                conversation_context="",
                additional_context="",
            ):
                if agent_slug == "safety":
                    return SafetyAssessmentResult(
                        crisis_resolution="unresolved",
                        risk_level="crisis",
                        relevant_risk_categories=[
                            "suicide_or_self_harm",
                        ],
                        recommended_action="handoff",
                    )

                if agent_slug == "crisis":
                    return (
                        "I’m taking what you said seriously. "
                        "Please get immediate real-world support."
                    )

                if agent_slug == "output_safety":
                    return OutputSafetyDecision(
                        action="allow",
                        reason="",
                        revised_response="",
                    )

                if agent_slug == "supervisor":
                    raise AssertionError("Supervisor must not be called for a crisis message.")

                raise AssertionError(f"Unexpected agent: {agent_slug}")

            mock_run_agent.side_effect = run_agent_side_effect

            response = self.client.post(
                reverse(
                    "conversations:detail",
                    args=[conversation.pk],
                ),
                data={
                    "content": "I am afraid I might hurt myself tonight.",
                },
            )

        self.assertEqual(response.status_code, 302)

        conversation.refresh_from_db()

        self.assertEqual(
            conversation.mode,
            ConversationMode.CRISIS,
        )

        self.assertEqual(
            conversation.turn_state,
            ConversationTurnState.IDLE,
        )

        messages = list(conversation.messages.order_by("sequence_number"))

        self.assertEqual(len(messages), 2)

        self.assertEqual(
            messages[1].content,
            ("I’m taking what you said seriously. " "Please get immediate real-world support."),
        )

        called_agents = [call.kwargs["agent_slug"] for call in mock_run_agent.call_args_list]

        self.assertEqual(
            called_agents,
            [
                "safety",
                "crisis",
                "output_safety",
            ],
        )

        mock_save_handoff.assert_called_once()

    def test_output_safety_revision_reaches_user_as_final_response(self):
        conversation = self.create_conversation()

        original_draft = "Just move on. Everything happens for a reason."

        revised_response = (
            "It sounds like you're still affected by the breakup, "
            "and simply moving on may not feel that easy right now."
        )

        with (
            patch("orchestration.graph.save_safety_assessment"),
            patch("orchestration.graph.save_retrieval"),
            patch("orchestration.graph.save_handoff"),
            patch("orchestration.graph.run_agent") as mock_run_agent,
        ):

            def run_agent_side_effect(
                agent_slug,
                user_message,
                conversation_context="",
                additional_context="",
            ):
                if agent_slug == "safety":
                    return SafetyAssessmentResult(
                        crisis_resolution="not_applicable",
                        risk_level="normal",
                        relevant_risk_categories=[],
                        recommended_action="allow",
                    )

                if agent_slug == "supervisor":
                    return SupervisorDecision(
                        route="support",
                    )

                if agent_slug == "support":
                    return original_draft

                if agent_slug == "output_safety":
                    return OutputSafetyDecision(
                        action="revise",
                        reason="Dismissive generic response.",
                        revised_response=revised_response,
                    )

                raise AssertionError(f"Unexpected agent: {agent_slug}")

            mock_run_agent.side_effect = run_agent_side_effect

            response = self.client.post(
                reverse(
                    "conversations:detail",
                    args=[conversation.pk],
                ),
                data={
                    "content": "I can't stop thinking about my breakup.",
                },
            )

        self.assertEqual(response.status_code, 302)

        conversation.refresh_from_db()

        messages = list(conversation.messages.order_by("sequence_number"))

        self.assertEqual(len(messages), 2)

        self.assertEqual(
            messages[1].content,
            revised_response,
        )

        self.assertNotEqual(
            messages[1].content,
            original_draft,
        )

        called_agents = [call.kwargs["agent_slug"] for call in mock_run_agent.call_args_list]

        self.assertEqual(
            called_agents,
            [
                "safety",
                "supervisor",
                "support",
                "output_safety",
            ],
        )

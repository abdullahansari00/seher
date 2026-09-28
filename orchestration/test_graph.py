from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from conversations.choices import (
    ConversationMode,
    ConversationStatus,
    ConversationTurnState,
)
from conversations.models import Conversation
from conversations.services import create_user_message
from orchestration.execution import start_agent_run
from orchestration.graph import seher_graph
from orchestration.models import AIModelConfig, AgentConfig
from orchestration.schemas import (
    OutputSafetyDecision,
    SafetyAssessmentResult,
    SupervisorDecision,
)

User = get_user_model()


class SeherGraphTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="graph_test_user",
            email="graph_test@example.com",
            password="test-password",
        )

        self.model_config = AIModelConfig.objects.create(
            name="graph-test-model",
            provider="gemini",
            model_name="test-model",
            purpose="chat",
            temperature=0.7,
            max_output_tokens=512,
            timeout_seconds=30,
            enabled=True,
            is_default=False,
        )

        self._create_agent("safety", temperature=0)
        self._create_agent("supervisor", temperature=0)
        self._create_agent("support", temperature=0.7)
        self._create_agent("crisis", temperature=0.7)
        self._create_agent("output_safety", temperature=0)

    def _create_agent(self, slug, temperature):
        return AgentConfig.objects.create(
            slug=slug,
            name=slug.replace("_", " ").title(),
            description=f"Test {slug} agent.",
            system_prompt=f"You are the test {slug} agent.",
            model_config=self.model_config,
            temperature=temperature,
            enabled=True,
            version=1,
        )

    def _create_run(self, content="I am having a difficult day."):
        conversation = Conversation.objects.create(
            user=self.user,
            status=ConversationStatus.ACTIVE,
            mode=ConversationMode.NORMAL,
            turn_state=ConversationTurnState.IDLE,
        )

        message = create_user_message(
            conversation=conversation,
            content=content,
        )

        agent_run = start_agent_run(
            conversation=conversation,
            message=message,
        )

        return conversation, message, agent_run

    def _invoke(
        self,
        *,
        user_message,
        agent_run,
        conversation,
        run_agent_side_effect,
        retrieve_chunks=None,
        evaluation_mode=False,
    ):
        if retrieve_chunks is None:
            retrieve_chunks = []

        with (
            patch(
                "orchestration.graph.run_agent",
                side_effect=run_agent_side_effect,
            ) as mock_run_agent,
            patch(
                "orchestration.graph.retrieve_chunks",
                return_value=retrieve_chunks,
            ) as mock_retrieve_chunks,
            patch(
                "orchestration.graph.save_safety_assessment",
            ),
            patch(
                "orchestration.graph.save_retrieval",
            ),
            patch(
                "orchestration.graph.save_handoff",
            ) as mock_save_handoff,
            patch(
                "orchestration.graph.get_crisis_resources",
                return_value={
                    "country": "TEST",
                    "resources": [
                        {
                            "id": "test_emergency",
                            "name": "Test Emergency Service",
                            "purpose": "Immediate emergency assistance",
                            "phone": "999",
                        }
                    ],
                },
            ) as mock_get_crisis_resources,
            patch(
                "orchestration.graph.create_agent_step",
                return_value=(Mock(), Mock()),
            ),
            patch(
                "orchestration.graph.complete_agent_step",
            ),
            patch(
                "orchestration.graph.fail_agent_step",
            ),
        ):
            result = seher_graph.invoke(
                {
                    "conversation_id": conversation.id,
                    "user_message_id": user_message.id,
                    "user_message": user_message.content,
                    "agent_run_id": agent_run.id,
                    "conversation_mode": conversation.mode,
                    "evaluation_mode": evaluation_mode,
                    "conversation_context": "",
                    "safety_assessment": {},
                    "safety_route": "normal",
                    "workflow_route": "support",
                    "retrieved_context": [],
                    "response": "",
                    "end_node": "",
                }
            )

        return (
            result,
            mock_run_agent,
            mock_retrieve_chunks,
            mock_save_handoff,
        )

    def test_normal_support_path(self):
        conversation, message, agent_run = self._create_run("I feel lonely today.")

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
                return SupervisorDecision(route="support")

            if agent_slug == "support":
                return "That sounds like a lonely day."

            if agent_slug == "output_safety":
                return OutputSafetyDecision(
                    action="allow",
                    reason="",
                    revised_response="",
                )

            raise AssertionError(f"Unexpected agent call: {agent_slug}")

        (
            result,
            mock_run_agent,
            mock_retrieve_chunks,
            mock_save_handoff,
        ) = self._invoke(
            user_message=message,
            agent_run=agent_run,
            conversation=conversation,
            run_agent_side_effect=run_agent_side_effect,
        )

        self.assertEqual(
            result["safety_route"],
            "normal",
        )

        self.assertEqual(
            result["workflow_route"],
            "support",
        )

        self.assertEqual(
            result["response"],
            "That sounds like a lonely day.",
        )

        self.assertEqual(
            result["end_node"],
            "output_safety",
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

        mock_retrieve_chunks.assert_not_called()
        mock_save_handoff.assert_not_called()

    def test_normal_knowledge_path_uses_rag(self):
        conversation, message, agent_run = self._create_run(
            "Why does my mind keep replaying a breakup?"
        )

        retrieved_chunks = [
            {
                "content": (
                    "Breakup-related rumination can involve repeatedly "
                    "replaying memories and conversations."
                ),
                "metadata": {
                    "document_id": 1,
                    "chunk_id": 10,
                },
            }
        ]

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
                return SupervisorDecision(route="knowledge")

            if agent_slug == "support":
                return "It can be common for the mind to repeatedly revisit a breakup."

            if agent_slug == "output_safety":
                return OutputSafetyDecision(
                    action="allow",
                    reason="",
                    revised_response="",
                )

            raise AssertionError(f"Unexpected agent call: {agent_slug}")

        (
            result,
            mock_run_agent,
            mock_retrieve_chunks,
            mock_save_handoff,
        ) = self._invoke(
            user_message=message,
            agent_run=agent_run,
            conversation=conversation,
            run_agent_side_effect=run_agent_side_effect,
            retrieve_chunks=retrieved_chunks,
        )

        self.assertEqual(
            result["safety_route"],
            "normal",
        )

        self.assertEqual(
            result["workflow_route"],
            "knowledge",
        )

        self.assertEqual(
            result["retrieved_context"],
            retrieved_chunks,
        )

        self.assertEqual(
            result["response"],
            "It can be common for the mind to repeatedly revisit a breakup.",
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

        mock_retrieve_chunks.assert_called_once()

        mock_save_handoff.assert_not_called()

    def test_crisis_path_bypasses_supervisor_and_hands_off_to_crisis(self):
        conversation, message, agent_run = self._create_run(
            "I am afraid I might hurt myself tonight."
        )

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
                    relevant_risk_categories=["suicide_or_self_harm"],
                    recommended_action="handoff",
                )

            if agent_slug == "crisis":
                return (
                    "I am taking what you said seriously. Please get immediate real-world support."
                )

            if agent_slug == "output_safety":
                return OutputSafetyDecision(
                    action="allow",
                    reason="",
                    revised_response="",
                )

            if agent_slug == "supervisor":
                raise AssertionError("Supervisor must not run for a crisis route.")

            raise AssertionError(f"Unexpected agent call: {agent_slug}")

        (
            result,
            mock_run_agent,
            mock_retrieve_chunks,
            mock_save_handoff,
        ) = self._invoke(
            user_message=message,
            agent_run=agent_run,
            conversation=conversation,
            run_agent_side_effect=run_agent_side_effect,
        )

        self.assertEqual(
            result["safety_route"],
            "crisis",
        )

        self.assertEqual(
            result["response"],
            "I am taking what you said seriously. Please get immediate real-world support.",
        )

        self.assertEqual(
            result["end_node"],
            "output_safety",
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

        mock_retrieve_chunks.assert_not_called()
        mock_save_handoff.assert_called_once()

        conversation.refresh_from_db()

        self.assertEqual(
            conversation.mode,
            ConversationMode.CRISIS,
        )

    def test_output_safety_block_replaces_unsafe_draft(self):
        conversation, message, agent_run = self._create_run("I feel terrible.")

        unsafe_draft = "You don't need anyone else. You have me, and I'll always be here."

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
                return SupervisorDecision(route="support")

            if agent_slug == "support":
                return unsafe_draft

            if agent_slug == "output_safety":
                return OutputSafetyDecision(
                    action="block",
                    reason="Dependency/exclusivity language.",
                    revised_response="",
                )

            raise AssertionError(f"Unexpected agent call: {agent_slug}")

        result, _, _, _ = self._invoke(
            user_message=message,
            agent_run=agent_run,
            conversation=conversation,
            run_agent_side_effect=run_agent_side_effect,
        )

        self.assertNotEqual(
            result["response"],
            unsafe_draft,
        )

        self.assertEqual(
            result["response"],
            "I'm sorry, I can't provide that response safely.",
        )

    def test_output_safety_revise_returns_rewritten_response(self):
        conversation, message, agent_run = self._create_run(
            "I cannot stop thinking about my breakup."
        )

        original_draft = "Just move on. Everything happens for a reason."

        revised_response = (
            "It sounds like your mind is still caught up in the breakup. "
            "That can make it difficult to simply move forward."
        )

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
                return SupervisorDecision(route="support")

            if agent_slug == "support":
                return original_draft

            if agent_slug == "output_safety":
                return OutputSafetyDecision(
                    action="revise",
                    reason="Dismissive generic response.",
                    revised_response=revised_response,
                )

            raise AssertionError(f"Unexpected agent call: {agent_slug}")

        result, _, _, _ = self._invoke(
            user_message=message,
            agent_run=agent_run,
            conversation=conversation,
            run_agent_side_effect=run_agent_side_effect,
        )

        self.assertEqual(
            result["response"],
            revised_response,
        )

        self.assertNotEqual(
            result["response"],
            original_draft,
        )

from unittest.mock import patch

from django.test import TestCase

from .choices import ModelProvider, ModelPurpose
from .models import AIModelConfig, AgentConfig
from .schemas import SupervisorDecision
from .services import get_agent_config, run_agent, OrchestrationError


class OrchestrationServiceTests(TestCase):
    def setUp(self):
        self.model_config = AIModelConfig.objects.create(
            name="test-chat-model",
            provider=ModelProvider.GEMINI,
            model_name="test-model",
            purpose=ModelPurpose.CHAT,
            temperature=0.7,
            max_output_tokens=512,
            timeout_seconds=30,
            is_default=False,
            enabled=True,
        )

    def create_agent(
        self,
        *,
        slug,
        temperature=0.7,
        system_prompt="You are a test agent.",
    ):
        return AgentConfig.objects.create(
            slug=slug,
            name=slug.replace("_", " ").title(),
            description="Test agent.",
            system_prompt=system_prompt,
            model_config=self.model_config,
            temperature=temperature,
            enabled=True,
            version=1,
        )

    def test_get_agent_config_returns_enabled_agent(self):
        agent = self.create_agent(
            slug="test_support",
        )

        result = get_agent_config("test_support")

        self.assertEqual(
            result.pk,
            agent.pk,
        )

    def test_get_agent_config_rejects_disabled_agent(self):
        self.create_agent(
            slug="disabled_agent",
        )

        AgentConfig.objects.filter(slug="disabled_agent").update(enabled=False)

        with self.assertRaisesMessage(
            OrchestrationError,
            "Enabled agent 'disabled_agent' was not found.",
        ):
            get_agent_config("disabled_agent")

    @patch("orchestration.services.generate_response")
    def test_run_agent_builds_prompt_with_context_and_user_message(
        self,
        mock_generate_response,
    ):
        mock_generate_response.return_value = "Test response."

        self.create_agent(
            slug="test_support",
            temperature=0.7,
            system_prompt="You are a supportive test agent.",
        )

        response = run_agent(
            agent_slug="test_support",
            user_message="I am having a difficult day.",
            conversation_context=("The user has been under work stress."),
        )

        self.assertEqual(
            response,
            "Test response.",
        )

        mock_generate_response.assert_called_once()

        call = mock_generate_response.call_args

        prompt = call.args[0]

        self.assertIn(
            "You are a supportive test agent.",
            prompt,
        )

        self.assertIn(
            "The user has been under work stress.",
            prompt,
        )

        self.assertIn(
            "I am having a difficult day.",
            prompt,
        )

        self.assertEqual(
            call.kwargs["model_config"],
            self.model_config,
        )

        self.assertEqual(
            call.kwargs["temperature"],
            0.7,
        )

        self.assertIsNone(
            call.kwargs["response_schema"],
        )

    @patch("orchestration.services.generate_response")
    def test_supervisor_uses_structured_output_schema(
        self,
        mock_generate_response,
    ):
        mock_generate_response.return_value = SupervisorDecision(route="support")

        self.create_agent(
            slug="supervisor",
            temperature=0,
            system_prompt="You are Seher's supervisor.",
        )

        response = run_agent(
            agent_slug="supervisor",
            user_message="I need to talk.",
        )

        self.assertEqual(
            response.route,
            "support",
        )

        mock_generate_response.assert_called_once()

        self.assertIs(
            mock_generate_response.call_args.kwargs["response_schema"],
            SupervisorDecision,
        )

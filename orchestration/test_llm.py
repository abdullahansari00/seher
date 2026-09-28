from unittest.mock import patch

import httpx
from google import genai
from django.test import SimpleTestCase

from .llm import LLMError, generate_response
from .models import AIModelConfig


class LLMRetryTests(SimpleTestCase):
    def request_with_statuses(self, statuses):
        calls = []
        real_client = genai.Client

        def handler(request):
            status = statuses[min(len(calls), len(statuses) - 1)]
            calls.append(request)
            if status != 200:
                return httpx.Response(
                    status, json={"error": {"code": status, "message": "Test error"}}
                )
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {"content": {"role": "model", "parts": [{"text": "Recovered response"}]}}
                    ]
                },
            )

        def client_factory(**kwargs):
            kwargs["http_options"].httpx_client = httpx.Client(
                transport=httpx.MockTransport(handler)
            )
            client = real_client(**kwargs)
            client._api_client._retry.sleep = lambda seconds: None
            return client

        config = AIModelConfig(
            name="test", provider="gemini", model_name="test-model", api_key_plaintext="test-key"
        )
        return calls, config, patch("orchestration.llm.genai.Client", side_effect=client_factory)

    def test_deadline_error_retries_and_recovers(self):
        calls, config, client = self.request_with_statuses([504, 200])
        with client:
            self.assertEqual(generate_response("Hello", model_config=config), "Recovered response")
        self.assertEqual(len(calls), 2)

    def test_persistent_error_stops_after_three_attempts(self):
        calls, config, client = self.request_with_statuses([504])
        with client, self.assertRaises(LLMError):
            generate_response("Hello", model_config=config)
        self.assertEqual(len(calls), 3)

    def test_invalid_request_is_not_retried(self):
        calls, config, client = self.request_with_statuses([400])
        with client, self.assertRaises(LLMError):
            generate_response("Hello", model_config=config)
        self.assertEqual(len(calls), 1)

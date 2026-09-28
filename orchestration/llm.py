import logging
from typing import TypeVar

from django.core.exceptions import ImproperlyConfigured
from google import genai
from google.genai import types
from pydantic import BaseModel

from .models import AIModelConfig

logger = logging.getLogger("seher.orchestration")


class LLMError(Exception):
    """Raised when an LLM request cannot be completed."""


T = TypeVar("T", bound=BaseModel)


def get_active_chat_model() -> AIModelConfig:
    config = AIModelConfig.objects.filter(
        enabled=True,
        is_default=True,
        purpose="chat",
    ).first()

    if not config:
        raise ImproperlyConfigured("No default enabled chat model is configured.")

    if config.provider != "gemini":
        raise ImproperlyConfigured(f"Unsupported provider: {config.provider}")

    if not config.api_key_plaintext:
        raise ImproperlyConfigured(f"No API key configured for '{config.name}'.")

    return config


def generate_response(
    prompt: str,
    *,
    model_config: AIModelConfig | None = None,
    temperature: float | None = None,
    response_schema: type[T] | None = None,
) -> str | T:
    config = model_config or get_active_chat_model()

    if not config.enabled:
        raise ImproperlyConfigured(f"Model configuration '{config.name}' is disabled.")

    if config.provider != "gemini":
        raise ImproperlyConfigured(f"Unsupported provider: {config.provider}")

    if not config.api_key_plaintext:
        raise ImproperlyConfigured(f"No API key configured for '{config.name}'.")

    generation_config = types.GenerateContentConfig(
        temperature=(config.temperature if temperature is None else temperature),
        max_output_tokens=config.max_output_tokens,
    )

    if response_schema:
        generation_config.response_mime_type = "application/json"
        generation_config.response_schema = response_schema

    logger.info(
        "LLM request started | model=%s purpose=%s structured=%s",
        config.model_name,
        config.purpose,
        response_schema is not None,
    )

    try:
        with genai.Client(
            api_key=config.api_key_plaintext,
            http_options=types.HttpOptions(
                timeout=config.timeout_seconds * 1000,
                retry_options=types.HttpRetryOptions(
                    attempts=3,
                    initial_delay=1,
                    max_delay=4,
                    exp_base=2,
                    jitter=1,
                    http_status_codes=[408, 429, 500, 502, 503, 504],
                ),
            ),
        ) as client:
            response = client.models.generate_content(
                model=config.model_name,
                contents=prompt,
                config=generation_config,
            )

    except Exception as exc:
        logger.exception(
            "LLM request failed | model=%s purpose=%s",
            config.model_name,
            config.purpose,
        )

        raise LLMError(f"LLM request failed for model '{config.name}'.") from exc

    logger.info(
        "LLM request completed | model=%s purpose=%s structured=%s",
        config.model_name,
        config.purpose,
        response_schema is not None,
    )

    if not response.text:
        raise LLMError("Gemini returned an empty response.")

    if response_schema:
        try:
            return response_schema.model_validate_json(response.text)
        except Exception as exc:
            logger.exception(
                "Structured LLM output validation failed | " "model=%s purpose=%s",
                config.model_name,
                config.purpose,
            )

            raise LLMError(
                "Gemini returned structured output that " "could not be validated."
            ) from exc

    return response.text

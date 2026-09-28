from django.core.exceptions import ImproperlyConfigured
from google import genai
from google.genai import types

from orchestration.models import AIModelConfig


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""


def get_embedding_config() -> AIModelConfig:
    config = AIModelConfig.objects.filter(
        enabled=True,
        is_default=True,
        purpose="embeddings",
    ).first()

    if not config:
        raise ImproperlyConfigured("No default enabled embedding model is configured.")

    if config.provider != "gemini":
        raise ImproperlyConfigured(f"Unsupported embedding provider: {config.provider}")

    if not config.api_key_plaintext:
        raise ImproperlyConfigured(f"No API key configured for '{config.name}'.")

    return config


def embed_text(text: str) -> list[float]:
    if not text.strip():
        raise EmbeddingError("Cannot embed empty text.")

    config = get_embedding_config()

    client = genai.Client(
        api_key=config.api_key_plaintext,
    )

    result = client.models.embed_content(
        model=config.model_name,
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=768,
        ),
    )

    if not result.embeddings:
        raise EmbeddingError("Gemini returned no embeddings.")

    return result.embeddings[0].values

from django.db import models


class RunStatus(models.TextChoices):
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    HANDOFF = "handoff", "Handoff"


class StepStatus(models.TextChoices):
    STARTED = "started", "Started"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class StepType(models.TextChoices):
    ROUTE = "route", "Route"
    SAFETY = "safety", "Safety"
    RETRIEVE = "retrieve", "Retrieve"
    GENERATE = "generate", "Generate"
    HANDOFF = "handoff", "Handoff"


class ModelProvider(models.TextChoices):
    OPENAI = "openai", "OpenAI"
    GROQ = "groq", "Groq"
    ANTHROPIC = "anthropic", "Anthropic"
    GEMINI = "gemini", "Gemini"
    OLLAMA = "ollama", "Ollama"
    LOCAL = "local", "Local"


class ModelPurpose(models.TextChoices):
    CHAT = "chat", "Chat"
    EMBEDDINGS = "embeddings", "Embeddings"
    SAFETY = "safety", "Safety"
    EVAL = "eval", "Eval"

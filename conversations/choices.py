from django.db import models


class ConversationStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    CLOSED = "closed", "Closed"


class ConversationTurnState(models.TextChoices):
    IDLE = "idle", "Idle"
    WAITING_FOR_ASSISTANT = "waiting_for_assistant", "Waiting for assistant"


class MessageRole(models.TextChoices):
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"
    SYSTEM = "system", "System"
    TOOL = "tool", "Tool"


class ConversationMode(models.TextChoices):
    NORMAL = "normal", "Normal"
    CRISIS = "crisis", "Crisis"

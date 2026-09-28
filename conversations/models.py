from django.conf import settings
from django.db import models
from django.db.models import Q

from seher.common.models import TimeStampedModel

from .choices import ConversationStatus, ConversationTurnState, MessageRole, ConversationMode


class Conversation(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    status = models.CharField(
        max_length=16,
        choices=ConversationStatus.choices,
        default=ConversationStatus.ACTIVE,
        db_index=True,
    )
    mode = models.CharField(
        max_length=16,
        choices=ConversationMode.choices,
        default=ConversationMode.NORMAL,
        db_index=True,
    )
    turn_state = models.CharField(
        max_length=32,
        choices=ConversationTurnState.choices,
        default=ConversationTurnState.IDLE,
        db_index=True,
    )
    summary = models.TextField(blank=True, default="")
    last_summarized_user_message_sequence_number = models.PositiveIntegerField(default=0)
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    class Meta:
        verbose_name_plural = "Conversations"
        ordering = ("-last_message_at", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(status=ConversationStatus.ACTIVE),
                name="unique_active_conversation_per_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} ({self.status})"


class Message(TimeStampedModel):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(
        max_length=16,
        choices=MessageRole.choices,
        db_index=True,
    )
    sequence_number = models.PositiveIntegerField()
    content = models.TextField()

    ip_address = models.GenericIPAddressField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Messages"
        ordering = ("sequence_number", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "sequence_number"],
                name="unique_message_sequence_per_conversation",
            )
        ]
        indexes = [
            models.Index(fields=["conversation", "sequence_number"]),
        ]

    def __str__(self) -> str:
        return f"{self.conversation_id} #{self.sequence_number} {self.role}"

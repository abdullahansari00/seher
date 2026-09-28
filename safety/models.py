from django.db import models

from seher.common.models import TimeStampedModel

from .choices import AssessmentStage, RiskLevel, SafetyDecision


class SafetyPolicy(TimeStampedModel):
    code = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    policy_type = models.CharField(
        max_length=64,
        blank=True,
        help_text="Example: keyword, classifier, llm, hybrid",
    )
    enabled = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    rule_json = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Safety policies"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class SafetyAssessment(TimeStampedModel):
    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.CASCADE,
        related_name="safety_assessments",
    )
    message = models.ForeignKey(
        "conversations.Message",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="safety_assessments",
    )
    stage = models.CharField(
        max_length=16,
        choices=AssessmentStage.choices,
        db_index=True,
    )
    risk_level = models.CharField(
        max_length=16,
        choices=RiskLevel.choices,
        default=RiskLevel.NORMAL,
        db_index=True,
    )
    decision = models.CharField(
        max_length=16,
        choices=SafetyDecision.choices,
        default=SafetyDecision.ALLOW,
        db_index=True,
    )
    categories = models.JSONField(default=list, blank=True)
    policy = models.ForeignKey(
        SafetyPolicy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessments",
    )
    model_name = models.CharField(max_length=120, blank=True)
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Safety assessments"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["conversation", "stage"]),
            models.Index(fields=["risk_level", "decision"]),
        ]

    def __str__(self) -> str:
        return f"{self.conversation_id} {self.stage} {self.risk_level}"


class SafetyEvent(TimeStampedModel):
    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.CASCADE,
        related_name="safety_events",
    )
    assessment = models.ForeignKey(
        SafetyAssessment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    event_type = models.CharField(max_length=120)
    payload = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Safety events"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.event_type

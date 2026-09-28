from django.db import models

from seher.common.models import TimeStampedModel

from .choices import (
    ModelProvider,
    ModelPurpose,
    RunStatus,
    StepStatus,
    StepType,
)


class AIModelConfig(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    provider = models.CharField(
        max_length=64,
        choices=ModelProvider.choices,
        db_index=True,
    )
    model_name = models.CharField(max_length=120)
    api_key_plaintext = models.TextField(blank=True)
    base_url = models.URLField(blank=True)
    purpose = models.CharField(
        max_length=64,
        choices=ModelPurpose.choices,
        blank=True,
        db_index=True,
    )
    temperature = models.FloatField(default=0.7)
    max_output_tokens = models.PositiveIntegerField(default=1024)
    timeout_seconds = models.PositiveIntegerField(default=60)
    is_default = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "AI model configurations"
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name} ({self.provider}/{self.model_name})"


class AgentConfig(TimeStampedModel):
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    system_prompt = models.TextField()
    model_config = models.ForeignKey(
        AIModelConfig,
        on_delete=models.PROTECT,
        related_name="agents",
    )
    temperature = models.FloatField(default=0.7)
    enabled = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Agent configurations"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class AgentRun(TimeStampedModel):
    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.CASCADE,
        related_name="agent_runs",
    )
    triggering_message = models.ForeignKey(
        "conversations.Message",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_runs",
    )
    supervisor_agent = models.ForeignKey(
        AgentConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supervised_runs",
    )
    graph_version = models.CharField(max_length=64, blank=True)
    supervisor_decision = models.CharField(max_length=128, blank=True)
    start_node = models.CharField(max_length=128, blank=True)
    end_node = models.CharField(max_length=128, blank=True)
    status = models.CharField(
        max_length=16,
        choices=RunStatus.choices,
        default=RunStatus.RUNNING,
        db_index=True,
    )
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    final_output = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Agent runs"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["conversation", "status"]),
        ]

    def __str__(self) -> str:
        return f"Run {self.id} ({self.status})"


class AgentStep(TimeStampedModel):
    agent_run = models.ForeignKey(
        AgentRun,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    step_order = models.PositiveIntegerField()
    node_name = models.CharField(max_length=128)
    agent_name = models.CharField(max_length=128, blank=True)
    step_type = models.CharField(
        max_length=32,
        choices=StepType.choices,
        default=StepType.ROUTE,
        db_index=True,
    )
    status = models.CharField(
        max_length=16,
        choices=StepStatus.choices,
        default=StepStatus.STARTED,
        db_index=True,
    )
    model_name = models.CharField(max_length=120, blank=True)
    input_payload = models.JSONField(default=dict, blank=True)
    output_payload = models.JSONField(default=dict, blank=True)
    tokens_input = models.PositiveIntegerField(null=True, blank=True)
    tokens_output = models.PositiveIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Agent steps"
        ordering = ("agent_run", "step_order")
        constraints = [
            models.UniqueConstraint(
                fields=["agent_run", "step_order"],
                name="unique_step_order_per_run",
            )
        ]

    def __str__(self) -> str:
        return f"Run {self.agent_run_id} step {self.step_order}"


class Handoff(TimeStampedModel):
    agent_run = models.ForeignKey(
        AgentRun,
        on_delete=models.CASCADE,
        related_name="handoffs",
    )
    from_agent = models.ForeignKey(
        AgentConfig,
        on_delete=models.PROTECT,
        related_name="handoffs_from",
    )
    to_agent = models.ForeignKey(
        AgentConfig,
        on_delete=models.PROTECT,
        related_name="handoffs_to",
    )
    reason = models.TextField()
    triggered_by_step = models.ForeignKey(
        AgentStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="handoffs",
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Handoffs"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.from_agent} → {self.to_agent}"

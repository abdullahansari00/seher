from django.conf import settings
from django.db import models

from seher.common.models import TimeStampedModel

from .choices import EvaluationRunStatus, EvaluationRunType


class EvaluationDataset(TimeStampedModel):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    version = models.CharField(max_length=64, default="1.0")
    source = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Evaluation datasets"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class EvaluationCase(TimeStampedModel):
    dataset = models.ForeignKey(
        EvaluationDataset,
        on_delete=models.CASCADE,
        related_name="cases",
    )
    case_id = models.SlugField(max_length=120)
    input_text = models.TextField()

    expected_output = models.TextField(blank=True)
    expected_route = models.CharField(max_length=120, blank=True)
    expected_risk_level = models.CharField(max_length=16, blank=True)
    expected_document = models.ForeignKey(
        "knowledge.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluation_cases",
    )

    conversation_turns = models.JSONField(default=list, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Evaluation cases"
        ordering = ("dataset", "case_id")
        constraints = [
            models.UniqueConstraint(
                fields=["dataset", "case_id"],
                name="unique_case_id_per_dataset",
            )
        ]

    def __str__(self) -> str:
        return f"{self.dataset.name}:{self.case_id}"


class EvaluationRun(TimeStampedModel):
    name = models.CharField(max_length=150)
    dataset = models.ForeignKey(
        EvaluationDataset,
        on_delete=models.PROTECT,
        related_name="runs",
    )
    run_type = models.CharField(
        max_length=16,
        choices=EvaluationRunType.choices,
        default=EvaluationRunType.OFFLINE,
        db_index=True,
    )
    status = models.CharField(
        max_length=16,
        choices=EvaluationRunStatus.choices,
        default=EvaluationRunStatus.PENDING,
        db_index=True,
    )
    model_config = models.ForeignKey(
        "orchestration.AIModelConfig",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluation_runs",
    )
    agent_config = models.ForeignKey(
        "orchestration.AgentConfig",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluation_runs",
    )
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluation_runs",
    )
    config_snapshot = models.JSONField(default=dict, blank=True)
    metrics_summary = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Evaluation runs"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.name


class EvaluationResult(TimeStampedModel):
    evaluation_run = models.ForeignKey(
        EvaluationRun,
        on_delete=models.CASCADE,
        related_name="results",
    )
    evaluation_case = models.ForeignKey(
        EvaluationCase,
        on_delete=models.CASCADE,
        related_name="results",
    )

    score = models.FloatField(default=0.0)
    passed = models.BooleanField(default=False)

    retrieval_passed = models.BooleanField(
        null=True,
        blank=True,
    )

    grounding_passed = models.BooleanField(
        null=True,
        blank=True,
    )

    grounding_explanation = models.TextField(
        blank=True,
    )

    memory_passed = models.BooleanField(
        null=True,
        blank=True,
    )

    memory_explanation = models.TextField(
        blank=True,
    )

    crisis_resource_passed = models.BooleanField(
        null=True,
        blank=True,
    )

    crisis_resource_explanation = models.TextField(
        blank=True,
    )

    prediction = models.TextField(blank=True)
    ground_truth = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Evaluation results"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["evaluation_run", "evaluation_case"],
                name="unique_result_per_case_per_run",
            )
        ]

    def __str__(self) -> str:
        return f"Run {self.evaluation_run_id} / Case {self.evaluation_case_id}"


class Metric(TimeStampedModel):
    evaluation_run = models.ForeignKey(
        EvaluationRun,
        on_delete=models.CASCADE,
        related_name="metrics",
    )
    name = models.CharField(max_length=120)
    value = models.FloatField()
    threshold = models.FloatField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Metrics"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["evaluation_run", "name"],
                name="unique_metric_name_per_run",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name}={self.value}"

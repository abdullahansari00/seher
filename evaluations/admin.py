from django.contrib import admin

from .models import (
    EvaluationCase,
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
    Metric,
)


class EvaluationCaseInline(admin.TabularInline):
    ordering = ("-id",)
    model = EvaluationCase
    extra = 0


@admin.register(EvaluationDataset)
class EvaluationDatasetAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "name",
        "version",
        "is_active",
        "created_at",
    )
    list_filter = (
        "is_active",
        "version",
        "created_at",
    )
    search_fields = (
        "name",
        "description",
        "source",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    inlines = [EvaluationCaseInline]


@admin.register(EvaluationCase)
class EvaluationCaseAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "dataset",
        "case_id",
        "expected_route",
        "expected_risk_level",
        "created_at",
    )
    list_filter = (
        "expected_route",
        "expected_risk_level",
        "created_at",
    )
    search_fields = (
        "case_id",
        "input_text",
        "expected_output",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("dataset",)


@admin.register(EvaluationRun)
class EvaluationRunAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "name",
        "dataset",
        "run_type",
        "status",
        "created_at",
    )
    list_filter = (
        "run_type",
        "status",
        "created_at",
    )
    search_fields = (
        "name",
        "notes",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    autocomplete_fields = (
        "dataset",
        "model_config",
        "agent_config",
        "started_by",
    )


@admin.register(EvaluationResult)
class EvaluationResultAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "evaluation_run",
        "evaluation_case",
        "score",
        "passed",
        "created_at",
    )
    list_filter = (
        "passed",
        "created_at",
    )
    search_fields = (
        "prediction",
        "ground_truth",
        "notes",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    autocomplete_fields = (
        "evaluation_run",
        "evaluation_case",
    )


@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "evaluation_run",
        "name",
        "value",
        "threshold",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = ("name",)
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("evaluation_run",)

from django.contrib import admin

from .models import SafetyAssessment, SafetyEvent, SafetyPolicy


@admin.register(SafetyPolicy)
class SafetyPolicyAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "code",
        "name",
        "policy_type",
        "enabled",
        "version",
        "created_at",
    )
    list_filter = (
        "policy_type",
        "enabled",
        "version",
        "created_at",
    )
    search_fields = (
        "code",
        "name",
        "description",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(SafetyAssessment)
class SafetyAssessmentAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "conversation",
        "stage",
        "risk_level",
        "decision",
        "model_name",
        "created_at",
    )
    list_filter = (
        "stage",
        "risk_level",
        "decision",
        "created_at",
    )
    search_fields = (
        "reason",
        "conversation__user__username",
        "conversation__user__email",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    autocomplete_fields = (
        "conversation",
        "message",
        "policy",
    )


@admin.register(SafetyEvent)
class SafetyEventAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "conversation",
        "event_type",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = (
        "event_type",
        "conversation__user__username",
        "conversation__user__email",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    autocomplete_fields = (
        "conversation",
        "assessment",
    )

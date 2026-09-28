from django.contrib import admin

from .models import AIModelConfig, AgentConfig, AgentRun, AgentStep, Handoff


@admin.register(AIModelConfig)
class AIModelConfigAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "name",
        "provider",
        "model_name",
        "purpose",
        "is_default",
        "enabled",
        "created_at",
    )
    list_filter = (
        "provider",
        "purpose",
        "is_default",
        "enabled",
        "created_at",
    )
    search_fields = (
        "name",
        "provider",
        "model_name",
        "purpose",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(AgentConfig)
class AgentConfigAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "slug",
        "name",
        "model_config",
        "enabled",
        "version",
        "created_at",
    )
    list_filter = (
        "enabled",
        "version",
        "created_at",
    )
    search_fields = (
        "slug",
        "name",
        "description",
        "system_prompt",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("model_config",)


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "conversation",
        "supervisor_agent",
        "status",
        "graph_version",
        "latency_ms",
        "created_at",
    )
    list_filter = (
        "status",
        "graph_version",
        "created_at",
    )
    search_fields = (
        "conversation__user__username",
        "conversation__user__email",
        "supervisor_decision",
        "start_node",
        "end_node",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    autocomplete_fields = (
        "conversation",
        "triggering_message",
        "supervisor_agent",
    )


@admin.register(AgentStep)
class AgentStepAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "agent_run",
        "step_order",
        "node_name",
        "step_type",
        "status",
        "created_at",
    )
    list_filter = (
        "step_type",
        "status",
        "created_at",
    )
    search_fields = (
        "node_name",
        "agent_name",
        "model_name",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("agent_run",)


@admin.register(Handoff)
class HandoffAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "agent_run",
        "from_agent",
        "to_agent",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = (
        "reason",
        "from_agent__name",
        "to_agent__name",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    autocomplete_fields = (
        "agent_run",
        "from_agent",
        "to_agent",
        "triggered_by_step",
    )

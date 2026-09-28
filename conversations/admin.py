from django.contrib import admin

from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "user",
        "status",
        "mode",
        "turn_state",
        "last_message_at",
        "closed_at",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "status",
        "mode",
        "turn_state",
        "created_at",
        "closed_at",
    )
    search_fields = (
        "user__username",
        "user__email",
        "metadata",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "last_message_at",
        "closed_at",
    )
    autocomplete_fields = ("user",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "conversation",
        "role",
        "sequence_number",
        "ip_address",
        "created_at",
    )
    list_filter = (
        "role",
        "created_at",
    )
    search_fields = (
        "content",
        "conversation__user__username",
        "conversation__user__email",
        "ip_address",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("conversation",)

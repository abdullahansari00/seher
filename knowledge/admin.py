from django.contrib import admin

from .models import Document, DocumentChunk, Retrieval, RetrievedDocument


class DocumentChunkInline(admin.TabularInline):
    ordering = ("-id",)
    model = DocumentChunk
    extra = 0
    fields = (
        "chunk_index",
        "token_count",
        "vector_id",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "title",
        "source_type",
        "status",
        "is_public",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "source_type",
        "status",
        "is_public",
        "created_at",
    )
    search_fields = (
        "title",
        "source_uri",
        "checksum",
        "raw_text",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    inlines = [DocumentChunkInline]


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "document",
        "chunk_index",
        "token_count",
        "vector_id",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = (
        "content",
        "vector_id",
        "document__title",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("document",)


@admin.register(Retrieval)
class RetrievalAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "conversation",
        "agent_run",
        "top_k",
        "retriever_name",
        "created_at",
    )
    list_filter = (
        "retriever_name",
        "created_at",
    )
    search_fields = (
        "query_text",
        "conversation__user__username",
        "conversation__user__email",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    autocomplete_fields = (
        "conversation",
        "agent_run",
    )


@admin.register(RetrievedDocument)
class RetrievedDocumentAdmin(admin.ModelAdmin):
    ordering = ("-id",)
    list_display = (
        "id",
        "retrieval",
        "rank",
        "score",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = (
        "retrieval__query_text",
        "chunk__content",
        "chunk__document__title",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    autocomplete_fields = (
        "retrieval",
        "chunk",
    )

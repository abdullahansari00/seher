from django.db import models

from seher.common.models import TimeStampedModel

from .choices import DocumentStatus, SourceType


class Document(TimeStampedModel):
    title = models.CharField(max_length=255, blank=True)
    source_type = models.CharField(
        max_length=32,
        choices=SourceType.choices,
        default=SourceType.MANUAL,
        db_index=True,
    )
    source_uri = models.TextField(blank=True)
    raw_text = models.TextField(blank=True)
    checksum = models.CharField(max_length=128, blank=True, db_index=True)
    status = models.CharField(
        max_length=16,
        choices=DocumentStatus.choices,
        default=DocumentStatus.PENDING,
        db_index=True,
    )
    is_public = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Documents"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["source_type"]),
        ]

    def __str__(self) -> str:
        return self.title or f"{self.source_type}:{self.id}"


class DocumentChunk(TimeStampedModel):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()
    token_count = models.PositiveIntegerField(default=0)
    vector_id = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Document chunks"
        ordering = ("document", "chunk_index")
        constraints = [
            models.UniqueConstraint(
                fields=["document", "chunk_index"],
                name="unique_chunk_index_per_document",
            )
        ]
        indexes = [
            models.Index(fields=["document", "chunk_index"]),
        ]

    def __str__(self) -> str:
        return f"{self.document_id} chunk {self.chunk_index}"


class Retrieval(TimeStampedModel):
    conversation = models.ForeignKey(
        "conversations.Conversation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retrievals",
    )
    agent_run = models.ForeignKey(
        "orchestration.AgentRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retrievals",
    )
    query_text = models.TextField()
    top_k = models.PositiveIntegerField(default=5)
    retriever_name = models.CharField(max_length=128, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Retrievals"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Retrieval {self.id}"


class RetrievedDocument(TimeStampedModel):
    retrieval = models.ForeignKey(
        Retrieval,
        on_delete=models.CASCADE,
        related_name="results",
    )
    chunk = models.ForeignKey(
        DocumentChunk,
        on_delete=models.CASCADE,
        related_name="retrieved_in",
    )
    rank = models.PositiveIntegerField()
    score = models.FloatField(default=0.0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Retrieved documents"
        ordering = ("rank",)
        constraints = [
            models.UniqueConstraint(
                fields=["retrieval", "rank"],
                name="unique_retrieval_rank",
            )
        ]

    def __str__(self) -> str:
        return f"{self.retrieval_id} → {self.rank}"

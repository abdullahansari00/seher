from django.db import models


class DocumentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"
    ARCHIVED = "archived", "Archived"


class SourceType(models.TextChoices):
    MANUAL = "manual", "Manual"
    WEBPAGE = "webpage", "Webpage"
    FILE = "file", "File"
    FAQ = "faq", "FAQ"
    NOTE = "note", "Note"

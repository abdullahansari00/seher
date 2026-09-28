from django.db import models


class EvaluationRunStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class EvaluationRunType(models.TextChoices):
    OFFLINE = "offline", "Offline"
    ONLINE = "online", "Online"
    REGRESSION = "regression", "Regression"
    SMOKE = "smoke", "Smoke"

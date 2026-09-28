from django.db import models


class RiskLevel(models.TextChoices):
    NORMAL = "normal", "Normal"
    CRISIS = "crisis", "Crisis"


class SafetyDecision(models.TextChoices):
    ALLOW = "allow", "Allow"
    HANDOFF = "handoff", "Handoff"


class AssessmentStage(models.TextChoices):
    INPUT = "input", "Input"
    OUTPUT = "output", "Output"

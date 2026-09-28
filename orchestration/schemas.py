from typing import Literal

from pydantic import BaseModel, Field


class SupervisorDecision(BaseModel):
    route: Literal["support", "knowledge"] = Field(
        description="The workflow that should handle the normal user message."
    )


class SafetyAssessmentResult(BaseModel):
    risk_level: Literal["normal", "crisis"]
    relevant_risk_categories: list[str] = Field(default_factory=list)
    recommended_action: Literal["allow", "handoff"]
    crisis_resolution: Literal[
        "not_applicable",
        "unresolved",
        "resolved",
    ]


class OutputSafetyDecision(BaseModel):
    action: Literal["allow", "revise", "block"]
    reason: str = ""
    revised_response: str = ""

import time
from typing import Optional

from .models import AgentConfig, AgentRun, AgentStep
from .choices import StepStatus


def create_agent_step(
    *,
    agent_run_id: int | None,
    step_order: int,
    node_name: str,
    step_type: str,
    agent: AgentConfig | None = None,
    input_payload: dict | None = None,
    evaluation_mode: bool = False,
) -> tuple[AgentStep | None, float | None]:
    if evaluation_mode or not agent_run_id:
        return None, None

    step = AgentStep.objects.create(
        agent_run_id=agent_run_id,
        step_order=step_order,
        node_name=node_name,
        agent_name=agent.name if agent else "",
        step_type=step_type,
        status=StepStatus.STARTED,
        model_name=(agent.model_config.model_name if agent else ""),
        input_payload=input_payload or {},
    )

    return step, time.perf_counter()


def complete_agent_step(
    step: AgentStep | None,
    started_at: float | None,
    *,
    output_payload: dict | None = None,
) -> None:
    if step is None or started_at is None:
        return

    step.status = StepStatus.COMPLETED
    step.latency_ms = int((time.perf_counter() - started_at) * 1000)
    step.output_payload = output_payload or {}

    step.save(
        update_fields=[
            "status",
            "latency_ms",
            "output_payload",
            "updated_at",
        ]
    )


def fail_agent_step(
    step: AgentStep | None,
    started_at: float | None,
    error: Exception,
) -> None:
    if step is None or started_at is None:
        return

    step.status = StepStatus.FAILED
    step.latency_ms = int((time.perf_counter() - started_at) * 1000)
    step.output_payload = {"error": str(error)}

    step.save(
        update_fields=[
            "status",
            "latency_ms",
            "output_payload",
            "updated_at",
        ]
    )

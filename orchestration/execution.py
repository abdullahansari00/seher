from django.utils import timezone

from .models import AgentRun

GRAPH_VERSION = "v1"


def start_agent_run(
    conversation,
    message,
) -> AgentRun:
    from .models import AgentConfig

    supervisor = AgentConfig.objects.filter(
        slug="supervisor",
        enabled=True,
    ).first()

    if not supervisor:
        raise RuntimeError("The enabled supervisor agent configuration was not found.")

    return AgentRun.objects.create(
        conversation=conversation,
        triggering_message=message,
        supervisor_agent=supervisor,
        graph_version=GRAPH_VERSION,
        start_node="safety_gate",
        status="running",
    )


def complete_agent_run(
    agent_run: AgentRun,
    *,
    result: dict,
) -> None:
    agent_run.status = "completed"
    agent_run.end_node = result.get("end_node", "")
    agent_run.final_output = result.get("response", "")

    agent_run.latency_ms = int((timezone.now() - agent_run.created_at).total_seconds() * 1000)

    agent_run.save(
        update_fields=[
            "status",
            "end_node",
            "final_output",
            "latency_ms",
            "updated_at",
        ]
    )


def fail_agent_run(
    agent_run: AgentRun,
    error: Exception,
) -> None:
    agent_run.status = "failed"
    agent_run.final_output = str(error)

    agent_run.latency_ms = int((timezone.now() - agent_run.created_at).total_seconds() * 1000)

    agent_run.save(
        update_fields=[
            "status",
            "final_output",
            "latency_ms",
            "updated_at",
        ]
    )

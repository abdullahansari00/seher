from .llm import generate_response
from .models import AgentConfig
from .schemas import (
    OutputSafetyDecision,
    SafetyAssessmentResult,
    SupervisorDecision,
)


class OrchestrationError(Exception):
    """Raised when Seher orchestration cannot complete."""


STRUCTURED_AGENT_SCHEMAS = {
    "supervisor": SupervisorDecision,
    "safety": SafetyAssessmentResult,
    "output_safety": OutputSafetyDecision,
}


def get_agent_config(agent_slug: str) -> AgentConfig:
    agent = (
        AgentConfig.objects.select_related("model_config")
        .filter(
            slug=agent_slug,
            enabled=True,
        )
        .first()
    )

    if not agent:
        raise OrchestrationError(f"Enabled agent '{agent_slug}' was not found.")

    return agent


def run_agent(
    agent_slug: str,
    user_message: str,
    conversation_context: str = "",
    additional_context: str = "",
    input_label: str = "User message",
):
    agent = get_agent_config(agent_slug)

    prompt_sections = [
        agent.system_prompt,
        f"Conversation context:\n{conversation_context or 'None'}",
    ]

    if additional_context:
        prompt_sections.append(f"Application-provided context:\n{additional_context}")

    prompt_sections.append(f"{input_label}:\n{user_message}")

    prompt = "\n\n".join(prompt_sections)

    schema = STRUCTURED_AGENT_SCHEMAS.get(agent_slug)

    return generate_response(
        prompt,
        model_config=agent.model_config,
        temperature=agent.temperature,
        response_schema=schema,
    )


def update_conversation_summary(
    *,
    existing_summary: str,
    new_user_messages_text: str,
) -> str:
    return run_agent(
        agent_slug="memory_summary",
        user_message=new_user_messages_text,
        conversation_context=existing_summary or "None",
    )

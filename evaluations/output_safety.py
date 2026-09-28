from orchestration.services import run_agent


def evaluate_output_safety(draft_response: str):
    return run_agent(
        agent_slug="output_safety",
        user_message=draft_response,
        input_label="Draft response to review",
    )

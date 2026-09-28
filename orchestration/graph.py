import json
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from knowledge.rag import retrieve_chunks

from .models import AgentConfig, AgentRun
from .persistence import save_handoff, save_retrieval, save_safety_assessment
from .services import run_agent
from .tracing import complete_agent_step, create_agent_step, fail_agent_step
from conversations.choices import ConversationMode
from conversations.models import Conversation
from safety.services import get_crisis_resources
import logging

logger = logging.getLogger("seher.orchestration")


RouteAfterSafety = Literal["normal", "crisis"]
WorkflowRoute = Literal["support", "knowledge"]


class SeherState(TypedDict):
    conversation_id: int
    user_message_id: int
    user_message: str
    agent_run_id: int

    conversation_mode: str
    evaluation_mode: bool
    conversation_context: str

    safety_assessment: dict
    safety_route: RouteAfterSafety
    workflow_route: WorkflowRoute

    retrieved_context: list[dict]
    response: str
    end_node: str


def safety_gate_node(state: SeherState) -> dict:
    agent = AgentConfig.objects.get(
        slug="safety",
        enabled=True,
    )

    step, started_at = create_agent_step(
        agent_run_id=state["agent_run_id"],
        step_order=1,
        node_name="safety_gate",
        step_type="safety",
        agent=agent,
        input_payload={
            "user_message": state["user_message"],
        },
        evaluation_mode=state["evaluation_mode"],
    )

    try:
        assessment = run_agent(
            agent_slug="safety",
            user_message=state["user_message"],
            conversation_context="",
        )

        assessment_data = assessment.model_dump()

        if not state["evaluation_mode"]:
            save_safety_assessment(
                conversation_id=state["conversation_id"],
                message_id=state["user_message_id"],
                assessment=assessment_data,
            )

        safety_route = "crisis" if assessment.risk_level == "crisis" else "normal"

        logger.info(
            "Safety route selected | run=%s route=%s",
            state["agent_run_id"],
            safety_route,
        )

        Conversation.objects.filter(pk=state["conversation_id"]).update(
            mode=(ConversationMode.CRISIS if safety_route == "crisis" else ConversationMode.NORMAL)
        )

        complete_agent_step(
            step,
            started_at,
            output_payload=assessment_data,
        )

        return {
            "safety_assessment": assessment_data,
            "safety_route": safety_route,
        }

    except Exception as exc:
        fail_agent_step(step, started_at, exc)
        raise


def supervisor_node(state: SeherState) -> dict:
    agent = AgentConfig.objects.get(
        slug="supervisor",
        enabled=True,
    )

    step, started_at = create_agent_step(
        agent_run_id=state["agent_run_id"],
        step_order=2,
        node_name="supervisor",
        step_type="route",
        agent=agent,
        input_payload={
            "user_message": state["user_message"],
        },
        evaluation_mode=state["evaluation_mode"],
    )

    try:
        decision = run_agent(
            agent_slug="supervisor",
            user_message=state["user_message"],
            conversation_context=state["conversation_context"],
        )

        if not state["evaluation_mode"]:
            AgentRun.objects.filter(id=state["agent_run_id"]).update(
                supervisor_decision=decision.route,
            )

        result = {
            "workflow_route": decision.route,
        }

        logger.info(
            "Workflow route selected | run=%s route=%s",
            state["agent_run_id"],
            decision.route,
        )

        complete_agent_step(
            step,
            started_at,
            output_payload=result,
        )

        return result

    except Exception as exc:
        fail_agent_step(step, started_at, exc)
        raise


def support_node(state: SeherState) -> dict:
    agent = AgentConfig.objects.get(
        slug="support",
        enabled=True,
    )

    step, started_at = create_agent_step(
        agent_run_id=state["agent_run_id"],
        step_order=3,
        node_name="support",
        step_type="generate",
        agent=agent,
        input_payload={
            "user_message": state["user_message"],
        },
        evaluation_mode=state["evaluation_mode"],
    )

    try:
        response = run_agent(
            agent_slug="support",
            user_message=state["user_message"],
            conversation_context=state["conversation_context"],
        )

        complete_agent_step(
            step,
            started_at,
            output_payload={
                "response": response,
            },
        )

        return {
            "response": response,
        }

    except Exception as exc:
        fail_agent_step(
            step,
            started_at,
            exc,
        )
        raise


def knowledge_node(state: SeherState) -> dict:
    agent = AgentConfig.objects.get(
        slug="support",
        enabled=True,
    )

    step, started_at = create_agent_step(
        agent_run_id=state["agent_run_id"],
        step_order=3,
        node_name="knowledge",
        step_type="retrieve",
        agent=agent,
        input_payload={
            "query": state["user_message"],
        },
        evaluation_mode=state["evaluation_mode"],
    )

    try:
        results = retrieve_chunks(
            state["user_message"],
            top_k=5,
        )

        if not state["evaluation_mode"]:
            save_retrieval(
                conversation_id=state["conversation_id"],
                agent_run_id=state["agent_run_id"],
                query=state["user_message"],
                results=results,
            )

        complete_agent_step(
            step,
            started_at,
            output_payload={
                "result_count": len(results),
            },
        )

        return {
            "retrieved_context": results,
        }

    except Exception as exc:
        fail_agent_step(
            step,
            started_at,
            exc,
        )
        raise


def knowledge_response_node(state: SeherState) -> dict:
    agent = AgentConfig.objects.get(
        slug="support",
        enabled=True,
    )

    step, started_at = create_agent_step(
        agent_run_id=state["agent_run_id"],
        step_order=4,
        node_name="knowledge_response",
        step_type="generate",
        agent=agent,
        input_payload={
            "user_message": state["user_message"],
            "retrieved_chunks": len(state["retrieved_context"]),
        },
        evaluation_mode=state["evaluation_mode"],
    )

    try:
        context = "\n\n".join(result["content"] for result in state["retrieved_context"])

        response = run_agent(
            agent_slug="support",
            user_message=f"""
User message:

{state["user_message"]}

Relevant trusted knowledge:

{context}

Use the relevant knowledge when it helps answer the user.
Do not mention the retrieval process.
Do not force irrelevant retrieved information into the response.
Respond naturally.
""".strip(),
            conversation_context=state["conversation_context"],
        )

        complete_agent_step(
            step,
            started_at,
            output_payload={
                "response": response,
            },
        )

        return {
            "response": response,
        }

    except Exception as exc:
        fail_agent_step(
            step,
            started_at,
            exc,
        )
        raise


def crisis_node(state: SeherState) -> dict:
    agent = AgentConfig.objects.get(
        slug="crisis",
        enabled=True,
    )

    step, started_at = create_agent_step(
        agent_run_id=state["agent_run_id"],
        step_order=2,
        node_name="crisis",
        step_type="handoff",
        agent=agent,
        input_payload={
            "user_message": state["user_message"],
            "safety_assessment": state["safety_assessment"],
        },
        evaluation_mode=state["evaluation_mode"],
    )

    try:
        if not state["evaluation_mode"]:
            save_handoff(
                agent_run_id=state["agent_run_id"],
                from_agent_slug="safety",
                to_agent_slug="crisis",
                reason=(
                    "Safety assessment classified the conversation "
                    "as requiring the crisis workflow."
                ),
                triggered_by_step=step,
            )

        resources = get_crisis_resources()

        crisis_resource_context = json.dumps(
            resources,
            ensure_ascii=False,
            indent=2,
        )

        response = run_agent(
            agent_slug="crisis",
            user_message=state["user_message"],
            conversation_context=state["conversation_context"],
            additional_context=(
                "This conversation is currently in crisis mode.\n\n"
                f"Safety assessment:\n{json.dumps(state['safety_assessment'], ensure_ascii=False, indent=2)}\n\n"
                "Available crisis resources supplied by the application:\n"
                f"{crisis_resource_context}\n\n"
                "Use only these resources. Do not invent, modify, or guess "
                "any emergency number, hotline, website, or other resource."
            ),
        )

        complete_agent_step(
            step,
            started_at,
            output_payload={
                "response": response,
            },
        )

        return {"response": response}

    except Exception as exc:
        fail_agent_step(
            step,
            started_at,
            exc,
        )
        raise


def output_safety_node(state: SeherState) -> dict:
    agent = AgentConfig.objects.get(
        slug="output_safety",
        enabled=True,
    )

    step_order = (
        3
        if state["safety_route"] == "crisis"
        else (4 if state["workflow_route"] == "support" else 5)
    )

    step, started_at = create_agent_step(
        agent_run_id=state["agent_run_id"],
        step_order=step_order,
        node_name="output_safety",
        step_type="safety",
        agent=agent,
        input_payload={
            "draft_response": state["response"],
        },
        evaluation_mode=state["evaluation_mode"],
    )

    try:
        decision = run_agent(
            agent_slug="output_safety",
            user_message=("Review the following draft response:\n\n" f"{state['response']}"),
            conversation_context="",
        )
        logger.info(
            "Output safety decision | run=%s action=%s",
            state["agent_run_id"],
            decision.action,
        )

        decision_data = decision.model_dump()

        complete_agent_step(
            step,
            started_at,
            output_payload=decision_data,
        )

        if decision.action == "block":
            response = "I'm sorry, I can't provide that response safely."

        elif decision.action == "revise":
            response = decision.revised_response.strip()

            if not response:
                response = "I'm sorry, I can't provide that response safely."

        else:
            response = state["response"]

        return {
            "response": response,
            "end_node": "output_safety",
        }

    except Exception as exc:
        fail_agent_step(step, started_at, exc)
        raise


def route_after_safety(state: SeherState) -> RouteAfterSafety:
    return state["safety_route"]


def route_after_supervisor(state: SeherState) -> WorkflowRoute:
    return state["workflow_route"]


def build_graph():
    graph = StateGraph(SeherState)

    graph.add_node("safety_gate", safety_gate_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("support", support_node)
    graph.add_node("knowledge", knowledge_node)
    graph.add_node("knowledge_response", knowledge_response_node)
    graph.add_node("crisis", crisis_node)
    graph.add_node("output_safety", output_safety_node)

    graph.add_edge(START, "safety_gate")

    graph.add_conditional_edges(
        "safety_gate",
        route_after_safety,
        {
            "normal": "supervisor",
            "crisis": "crisis",
        },
    )

    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "support": "support",
            "knowledge": "knowledge",
        },
    )

    graph.add_edge("knowledge", "knowledge_response")

    graph.add_edge("support", "output_safety")
    graph.add_edge("knowledge_response", "output_safety")
    graph.add_edge("crisis", "output_safety")

    graph.add_edge("output_safety", END)

    return graph.compile()


seher_graph = build_graph()

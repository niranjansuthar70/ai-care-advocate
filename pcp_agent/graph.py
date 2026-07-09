from __future__ import annotations

from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from pcp_agent.llm_extract import ExtractDiff, extract_update
from pcp_agent.merge import merge_state
from pcp_agent.patient import contact_patient
from pcp_agent.rules import decide_next_action
from pcp_agent.state import GraphState, NextAction, PCPCaseState

_checkpointer = MemorySaver()


def _extract_node(state: GraphState, *, model: str | None = None) -> dict[str, Any]:
    diff = extract_update(state.get("current_transcript"), state, model=model)
    return {"extract_diff": diff.model_dump()}


def _merge_node(state: GraphState) -> dict[str, Any]:
    raw = state.get("extract_diff")
    if not raw:
        raise RuntimeError("merge_state requires extract_diff from prior node")
    diff = ExtractDiff.model_validate(raw)
    return merge_state(state, state.get("current_transcript"), diff)


def _decide_node(state: GraphState) -> dict[str, Any]:
    raw = state.get("extract_diff")
    if not raw:
        raise RuntimeError("decide_next_action requires extract_diff from prior node")
    diff = ExtractDiff.model_validate(raw)
    return decide_next_action(state, diff)


def _contact_patient_node(state: GraphState) -> dict[str, Any]:
    action = NextAction(state["next_action"])
    return contact_patient(state, action)


def _followup_node(state: GraphState) -> dict[str, Any]:
    return {}


def _route_after_decide(state: GraphState) -> Literal["contact_patient", "followup"]:
    action = state.get("next_action")
    if action in {
        NextAction.DONE.value,
        NextAction.REJECTED.value,
        NextAction.GIVE_UP.value,
    }:
        return "contact_patient"
    return "followup"


def build_graph(*, model: str | None = None):
    def extract_with_model(state: GraphState) -> dict[str, Any]:
        return _extract_node(state, model=model)

    graph = StateGraph(GraphState)
    graph.add_node("extract_update", extract_with_model)
    graph.add_node("merge_state", _merge_node)
    graph.add_node("decide_next_action", _decide_node)
    graph.add_node("contact_patient", _contact_patient_node)
    graph.add_node("followup", _followup_node)

    graph.add_edge(START, "extract_update")
    graph.add_edge("extract_update", "merge_state")
    graph.add_edge("merge_state", "decide_next_action")
    graph.add_conditional_edges(
        "decide_next_action",
        _route_after_decide,
        {
            "contact_patient": "contact_patient",
            "followup": "followup",
        },
    )
    graph.add_edge("contact_patient", END)
    graph.add_edge("followup", END)

    return graph.compile(checkpointer=_checkpointer)


def run_turn(
    state: PCPCaseState,
    transcript: str,
    *,
    model: str | None = None,
) -> GraphState:
    graph = build_graph(model=model)
    thread_id = state["patient_id"]
    config = {"configurable": {"thread_id": thread_id}}

    input_state: GraphState = {
        **state,
        "current_transcript": transcript,
        "extract_diff": None,
    }

    return graph.invoke(input_state, config=config)

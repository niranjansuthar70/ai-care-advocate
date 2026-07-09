from __future__ import annotations

from pcp_agent.llm_extract import ExtractDiff, ExtractSignal
from pcp_agent.state import (
    MAX_FOLLOWUPS,
    NextAction,
    OrderStatus,
    PCPCaseState,
    record_followup_increment,
)


def is_wrong_code(state: PCPCaseState, diff: ExtractDiff) -> bool:
    if diff.signal == ExtractSignal.WRONG_CODE:
        return True
    return bool(diff.mentioned_code and diff.mentioned_code != state["billing_code"])


def is_done(state: PCPCaseState, diff: ExtractDiff) -> bool:
    if diff.signal != ExtractSignal.SUBMITTED:
        return False
    if diff.mentioned_code == state["billing_code"]:
        return True
    return state["order_status"] == OrderStatus.CONFIRMED.value


def decide_next_action(state: PCPCaseState, diff: ExtractDiff) -> dict:
    summary = diff.summary

    if is_wrong_code(state, diff):
        return {
            "next_action": NextAction.REJECTED.value,
            "last_decision_summary": summary,
        }

    if is_done(state, diff):
        return {
            "next_action": NextAction.DONE.value,
            "last_decision_summary": summary,
        }

    if state["followup_count"] >= MAX_FOLLOWUPS:
        return {
            "next_action": NextAction.GIVE_UP.value,
            "last_decision_summary": summary,
        }

    return {
        "next_action": NextAction.FOLLOWUP.value,
        "last_decision_summary": summary,
        **record_followup_increment(state),
    }

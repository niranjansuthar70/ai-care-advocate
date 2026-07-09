from __future__ import annotations

from datetime import datetime

from pcp_agent.llm_extract import ExtractDiff, ExtractSignal
from pcp_agent.state import (
    OrderStatus,
    PCPCaseState,
    append_transcript_update,
    record_turn_update,
)


def resolve_order_status(state: PCPCaseState, diff: ExtractDiff) -> str | None:
    if diff.mentioned_code and diff.mentioned_code != state["billing_code"]:
        return OrderStatus.CODE_MISMATCH.value

    if diff.signal == ExtractSignal.WRONG_CODE:
        return OrderStatus.CODE_MISMATCH.value

    if diff.signal == ExtractSignal.SUBMITTED:
        if diff.mentioned_code == state["billing_code"]:
            return OrderStatus.CONFIRMED.value
        return OrderStatus.SUBMITTED.value

    if diff.signal == ExtractSignal.NONE:
        return None

    signal_to_status = {
        ExtractSignal.ACKNOWLEDGED: OrderStatus.AWAITING_CONFIRMATION,
        ExtractSignal.STALLED: OrderStatus.STALLED,
        ExtractSignal.NO_ANSWER: OrderStatus.STALLED,
    }
    mapped = signal_to_status.get(diff.signal)
    return mapped.value if mapped else None


def merge_state(
    state: PCPCaseState,
    transcript: str | None,
    diff: ExtractDiff,
    *,
    now: datetime | None = None,
) -> dict:
    updates: dict = {}

    if transcript and transcript.strip():
        updates.update(record_turn_update(state, now=now))
        updates.update(append_transcript_update(state, transcript.strip()))

    new_status = resolve_order_status(state, diff)
    if new_status is not None:
        updates["order_status"] = new_status

    return updates

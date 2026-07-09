from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import TypedDict

MAX_FOLLOWUPS = 10


class OrderStatus(str, Enum):
    VERBAL_ONLY = "verbal_only"
    ORDER_REQUESTED = "order_requested"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    STALLED = "stalled"
    ESCALATED = "escalated"
    CODE_MISMATCH = "code_mismatch"


class NextAction(str, Enum):
    FOLLOWUP = "followup"
    DONE = "done"
    REJECTED = "rejected"
    GIVE_UP = "give_up"


class PCPCaseState(TypedDict):
    patient_id: str
    equipment: str
    billing_code: str
    pcp_name: str
    pcp_phone: str
    order_status: str
    last_contact_date: str | None
    contact_attempts: int
    followup_count: int
    transcript_log: list[str]
    next_action: str | None
    patient_informed: bool
    patient_message_draft: str | None
    last_decision_summary: str | None


class GraphState(PCPCaseState):
    current_transcript: str | None
    extract_diff: dict | None


def _utc_now(now: datetime | None = None) -> datetime:
    return now if now is not None else datetime.now(timezone.utc)


def new_case(
    patient_id: str,
    equipment: str,
    billing_code: str,
    pcp_name: str,
    pcp_phone: str,
) -> PCPCaseState:
    return PCPCaseState(
        patient_id=patient_id,
        equipment=equipment,
        billing_code=billing_code,
        pcp_name=pcp_name,
        pcp_phone=pcp_phone,
        order_status=OrderStatus.VERBAL_ONLY.value,
        last_contact_date=None,
        contact_attempts=0,
        followup_count=0,
        transcript_log=[],
        next_action=None,
        patient_informed=False,
        patient_message_draft=None,
        last_decision_summary=None,
    )


def days_since_last_contact(
    state: PCPCaseState,
    now: datetime | None = None,
) -> float | None:
    if state["last_contact_date"] is None:
        return None
    last = datetime.fromisoformat(state["last_contact_date"])
    current = _utc_now(now)
    return (current - last).total_seconds() / 86_400


def record_turn_update(
    state: PCPCaseState,
    now: datetime | None = None,
) -> dict:
    current = _utc_now(now)
    return {
        "last_contact_date": current.isoformat(),
        "contact_attempts": state["contact_attempts"] + 1,
    }


def record_followup_increment(state: PCPCaseState) -> dict:
    return {"followup_count": state["followup_count"] + 1}


def append_transcript_update(state: PCPCaseState, transcript: str) -> dict:
    return {"transcript_log": state["transcript_log"] + [transcript]}

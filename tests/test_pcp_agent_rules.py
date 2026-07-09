from __future__ import annotations

from datetime import datetime

from pcp_agent.llm_extract import ExtractDiff, ExtractSignal
from pcp_agent.state import (
    MAX_FOLLOWUPS,
    NextAction,
    OrderStatus,
    PCPCaseState,
    new_case,
    record_followup_increment,
)
from pcp_agent.rules import decide_next_action, is_done, is_wrong_code

ELEANOR = dict(
    patient_id="eleanor-martinez",
    equipment="standard manual wheelchair",
    billing_code="K0001",
    pcp_name="Dr. Sarah Chen",
    pcp_phone="312-555-0142",
)


def _acknowledged_diff() -> ExtractDiff:
    return ExtractDiff(
        signal=ExtractSignal.ACKNOWLEDGED,
        promised_followup_days=3,
        mentioned_code=None,
        summary="Verbal order noted; written order pending.",
    )


def _submitted_diff() -> ExtractDiff:
    return ExtractDiff(
        signal=ExtractSignal.SUBMITTED,
        promised_followup_days=None,
        mentioned_code="K0001",
        summary="Written order signed with K0001.",
    )


def _wrong_code_diff() -> ExtractDiff:
    return ExtractDiff(
        signal=ExtractSignal.WRONG_CODE,
        promised_followup_days=None,
        mentioned_code="K0002",
        summary="Signed order shows K0002.",
    )


def test_decide_followup_on_acknowledged():
    state = new_case(**ELEANOR)
    diff = _acknowledged_diff()

    result = decide_next_action(state, diff)

    assert result["next_action"] == NextAction.FOLLOWUP.value
    assert result["followup_count"] == 1


def test_decide_done_on_submitted_correct_code():
    state = new_case(**ELEANOR)
    diff = _submitted_diff()

    result = decide_next_action(state, diff)

    assert result["next_action"] == NextAction.DONE.value
    assert "followup_count" not in result


def test_decide_rejected_on_wrong_code():
    state = new_case(**ELEANOR)
    diff = _wrong_code_diff()

    result = decide_next_action(state, diff)

    assert result["next_action"] == NextAction.REJECTED.value


def test_decide_give_up_after_max_followups():
    state = new_case(**ELEANOR)
    state["followup_count"] = MAX_FOLLOWUPS
    diff = _acknowledged_diff()

    result = decide_next_action(state, diff)

    assert result["next_action"] == NextAction.GIVE_UP.value


def test_stalled_does_not_auto_reject():
    state = new_case(**ELEANOR)
    diff = ExtractDiff(
        signal=ExtractSignal.STALLED,
        promised_followup_days=None,
        mentioned_code=None,
        summary="Still no signed order.",
    )

    result = decide_next_action(state, diff)

    assert result["next_action"] == NextAction.FOLLOWUP.value


def test_is_wrong_code_detects_mentioned_code_mismatch():
    state = new_case(**ELEANOR)
    diff = ExtractDiff(
        signal=ExtractSignal.SUBMITTED,
        mentioned_code="K0002",
        promised_followup_days=None,
        summary="Order signed.",
    )

    assert is_wrong_code(state, diff) is True
    assert is_done(state, diff) is False

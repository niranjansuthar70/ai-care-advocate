from datetime import datetime, timedelta, timezone

from pcp_agent.state import (
    MAX_FOLLOWUPS,
    NextAction,
    OrderStatus,
    append_transcript_update,
    days_since_last_contact,
    new_case,
    record_followup_increment,
    record_turn_update,
)

ELEANOR = dict(
    patient_id="eleanor-martinez",
    equipment="standard manual wheelchair",
    billing_code="K0001",
    pcp_name="Dr. Sarah Chen",
    pcp_phone="312-555-0142",
)

FIXED_NOW = datetime(2026, 7, 9, 12, 0, 0, tzinfo=timezone.utc)


def test_new_case_eleanor_defaults():
    state = new_case(**ELEANOR)

    assert state["patient_id"] == "eleanor-martinez"
    assert state["order_status"] == OrderStatus.VERBAL_ONLY.value
    assert state["contact_attempts"] == 0
    assert state["followup_count"] == 0
    assert state["patient_informed"] is False
    assert state["patient_message_draft"] is None
    assert state["next_action"] is None


def test_record_turn_update_returns_diff_only():
    state = new_case(**ELEANOR)

    diff = record_turn_update(state, now=FIXED_NOW)

    assert set(diff.keys()) == {"last_contact_date", "contact_attempts"}
    assert diff["contact_attempts"] == 1
    assert state["contact_attempts"] == 0


def test_record_followup_increment():
    state = new_case(**ELEANOR)
    state["followup_count"] = 2

    diff = record_followup_increment(state)

    assert diff == {"followup_count": 3}
    assert state["followup_count"] == 2


def test_append_transcript_update_appends_without_mutating():
    state = new_case(**ELEANOR)
    state["transcript_log"] = ["first call"]

    diff = append_transcript_update(state, "front desk says order is being prepared")

    assert diff == {"transcript_log": ["first call", "front desk says order is being prepared"]}
    assert state["transcript_log"] == ["first call"]


def test_days_since_last_contact_none_when_never_contacted():
    state = new_case(**ELEANOR)

    assert days_since_last_contact(state, now=FIXED_NOW) is None


def test_days_since_last_contact_computes_delta():
    state = new_case(**ELEANOR)
    two_days_ago = FIXED_NOW - timedelta(days=2, hours=6)
    state["last_contact_date"] = two_days_ago.isoformat()

    assert days_since_last_contact(state, now=FIXED_NOW) == 2.25


def test_max_followups_constant():
    assert MAX_FOLLOWUPS == 10


def test_next_action_values():
    assert NextAction.FOLLOWUP.value == "followup"
    assert NextAction.DONE.value == "done"
    assert NextAction.REJECTED.value == "rejected"
    assert NextAction.GIVE_UP.value == "give_up"

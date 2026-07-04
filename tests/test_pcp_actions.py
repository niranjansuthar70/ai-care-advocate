from pathlib import Path

import pytest

from src.pcp.analyzers.scripted import ScriptedTranscriptAnalyzer
from src.pcp.engine.actions import ActionDecider, is_terminal_action, load_action_weights, weighted_pick
from src.pcp.engine.models import (
    CommunicationPhase,
    PcpAction,
    PcpCommunicationState,
    PcpTranscriptAnalysis,
    VerificationChecklist,
)
from src.shared.models import PatientContext, PcpContext

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"
INITIAL_TRANSCRIPT = FIXTURES / "pcp_initial.txt"


def test_order_signed_returns_close_signed():
    decider = ActionDecider()
    state = PcpCommunicationState(contact_count=1)
    action = decider.decide(
        state,
        PcpTranscriptAnalysis(order_signed=True),
        VerificationChecklist(),
    )
    assert action == PcpAction.CLOSE_SIGNED


def test_rejection_returns_close_rejected():
    decider = ActionDecider()
    state = PcpCommunicationState(contact_count=1)
    action = decider.decide(
        state,
        PcpTranscriptAnalysis(rejection_reason="declined"),
        VerificationChecklist(rejection_detected=True),
    )
    assert action == PcpAction.CLOSE_REJECTED


def test_max_contacts_returns_give_up():
    decider = ActionDecider(max_contacts=3)
    state = PcpCommunicationState(contact_count=3)
    action = decider.decide(
        state,
        PcpTranscriptAnalysis(),
        VerificationChecklist(patient_details_confirmed=True, order_details_confirmed=True),
    )
    assert action == PcpAction.GIVE_UP


def test_no_answer_uses_stochastic_bucket():
    decider = ActionDecider(rng_seed=42, weights={"no_answer": {"retry": 1.0, "nudge": 0.0}, "followup": {}})
    state = PcpCommunicationState(contact_count=1)
    action = decider.decide(
        state,
        PcpTranscriptAnalysis(no_answer=True),
        VerificationChecklist(),
    )
    assert action == PcpAction.RETRY


def test_missing_patient_verification():
    decider = ActionDecider()
    state = PcpCommunicationState(contact_count=1)
    action = decider.decide(
        state,
        PcpTranscriptAnalysis(),
        VerificationChecklist(order_details_confirmed=True),
    )
    assert action == PcpAction.VERIFY_PATIENT


def test_missing_order_verification():
    decider = ActionDecider()
    state = PcpCommunicationState(contact_count=1)
    action = decider.decide(
        state,
        PcpTranscriptAnalysis(),
        VerificationChecklist(patient_details_confirmed=True),
    )
    assert action == PcpAction.VERIFY_ORDER


def test_signed_phase_without_patient_informed():
    decider = ActionDecider()
    state = PcpCommunicationState(
        contact_count=2,
        current_phase=CommunicationPhase.SIGNED,
        patient_informed=False,
    )
    action = decider.decide(
        state,
        PcpTranscriptAnalysis(),
        VerificationChecklist(
            patient_details_confirmed=True,
            order_details_confirmed=True,
            followup_scheduled=True,
            closing_attempted=True,
        ),
    )
    assert action == PcpAction.INFORM_PATIENT


def test_initial_transcript_action_is_stochastic_followup():
    analyzer = ScriptedTranscriptAnalyzer()
    patient = PatientContext()
    pcp = PcpContext()
    text = INITIAL_TRANSCRIPT.read_text(encoding="utf-8")
    result = analyzer.extract(text, pcp=pcp, patient=patient)

    decider = ActionDecider(rng_seed=42, weights={"followup": {"nudge": 1.0, "schedule_followup": 0.0}, "no_answer": {}})
    state = PcpCommunicationState(contact_count=1)
    action = decider.decide(state, result.analysis, result.verification)
    assert action == PcpAction.NUDGE


def test_weighted_pick_is_reproducible_with_seed():
    weights = {"nudge": 0.6, "schedule_followup": 0.4}
    import random

    rng1 = random.Random(42 + 1)
    rng2 = random.Random(42 + 1)
    assert weighted_pick(rng1, weights) == weighted_pick(rng2, weights)


def test_load_action_weights_from_fixture():
    weights = load_action_weights()
    assert "followup" in weights
    assert weights["followup"]["nudge"] == 0.6


def test_is_terminal_action():
    assert is_terminal_action(PcpAction.CLOSE_SIGNED)
    assert is_terminal_action(PcpAction.GIVE_UP)
    assert not is_terminal_action(PcpAction.NUDGE)

from src.pcp.engine.models import (
    CommunicationPhase,
    PcpTranscriptAnalysis,
    VerificationChecklist,
)
from src.pcp.engine.state_machine import (
    apply_phase_to_state,
    derive_current_status,
    is_order_rejected,
    next_phase_after_call,
    next_phase_after_outcome,
    next_phase_after_patient_informed,
)


def test_order_signed_transitions_to_signed():
    phase = next_phase_after_call(
        CommunicationPhase.VERIFICATION,
        PcpTranscriptAnalysis(order_signed=True, summary="signed"),
        VerificationChecklist(),
        expected_code="K0001",
    )
    assert phase == CommunicationPhase.SIGNED


def test_wrong_billing_code_transitions_to_rejected():
    phase = next_phase_after_call(
        CommunicationPhase.FOLLOWUP,
        PcpTranscriptAnalysis(billing_code="K0002", summary="wrong code"),
        VerificationChecklist(),
        expected_code="K0001",
    )
    assert phase == CommunicationPhase.REJECTED


def test_order_in_queue_moves_to_followup():
    phase = next_phase_after_call(
        CommunicationPhase.VERIFICATION,
        PcpTranscriptAnalysis(order_in_queue=True, summary="in queue"),
        VerificationChecklist(patient_details_confirmed=True),
        expected_code="K0001",
    )
    assert phase == CommunicationPhase.FOLLOWUP


def test_partial_verification_stays_in_verification():
    phase = next_phase_after_call(
        CommunicationPhase.VERIFICATION,
        PcpTranscriptAnalysis(verbal_order_noted=True, summary="verbal only"),
        VerificationChecklist(patient_details_confirmed=True),
        expected_code="K0001",
    )
    assert phase == CommunicationPhase.VERIFICATION


def test_complete_verification_without_signed_moves_to_followup():
    verification = VerificationChecklist(
        patient_details_confirmed=True,
        order_details_confirmed=True,
        followup_scheduled=True,
        closing_attempted=True,
    )
    phase = next_phase_after_call(
        CommunicationPhase.VERIFICATION,
        PcpTranscriptAnalysis(summary="all verified, still pending"),
        verification,
        expected_code="K0001",
    )
    assert phase == CommunicationPhase.FOLLOWUP


def test_contact_limit_reached_transitions_to_rejected():
    phase = next_phase_after_call(
        CommunicationPhase.FOLLOWUP,
        PcpTranscriptAnalysis(summary="still waiting"),
        VerificationChecklist(),
        expected_code="K0001",
        contact_limit_reached=True,
    )
    assert phase == CommunicationPhase.REJECTED


def test_outcome_phases_advance_to_inform_patient():
    assert next_phase_after_outcome(CommunicationPhase.SIGNED) == CommunicationPhase.INFORM_PATIENT
    assert next_phase_after_outcome(CommunicationPhase.REJECTED) == CommunicationPhase.INFORM_PATIENT


def test_patient_informed_advances_to_closed():
    assert next_phase_after_patient_informed(CommunicationPhase.INFORM_PATIENT) == CommunicationPhase.CLOSED


def test_apply_phase_to_state_sets_order_signed_and_delta():
    from datetime import datetime, timedelta

    from src.pcp.engine.models import PcpCommunicationState

    state = PcpCommunicationState()
    t1 = datetime(2026, 7, 4, 10, 0, 0)
    t2 = datetime(2026, 7, 13, 10, 0, 0)
    state.record_contact(t1)
    state.record_contact(t2)

    apply_phase_to_state(state, CommunicationPhase.SIGNED)
    assert state.order_signed
    assert state.current_status == "written order signed"
    assert state.delta_conversion_time == timedelta(days=9)


def test_is_order_rejected_detects_verification_flag():
    assert is_order_rejected(
        PcpTranscriptAnalysis(),
        VerificationChecklist(rejection_detected=True),
        expected_code="K0001",
    )

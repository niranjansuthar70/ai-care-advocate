from datetime import datetime, timedelta

from src.pcp.engine.models import (
    CommunicationPhase,
    ContactStatus,
    PcpCommunicationState,
    VerificationChecklist,
    derive_order_signed,
)


def test_derive_order_signed_requires_matching_billing_code():
    assert derive_order_signed(
        written_order_submitted=True,
        billing_code="K0001",
        expected_code="K0001",
    )
    assert not derive_order_signed(
        written_order_submitted=True,
        billing_code="K0002",
        expected_code="K0001",
    )


def test_verification_checklist_merge_is_cumulative():
    prior = VerificationChecklist(patient_details_confirmed=True)
    incoming = VerificationChecklist(order_details_confirmed=True)
    merged = prior.merge(incoming)
    assert merged.patient_details_confirmed
    assert merged.order_details_confirmed


def test_record_contact_sets_first_contact_timestamps():
    state = PcpCommunicationState()
    t1 = datetime(2026, 7, 4, 10, 0, 0)
    t2 = datetime(2026, 7, 7, 10, 0, 0)

    state.record_contact(t1)
    assert state.contact_status == ContactStatus.CONTACTED
    assert state.contacted_at == t1
    assert state.last_communication_at == t1
    assert state.contact_count == 1

    state.record_contact(t2)
    assert state.contacted_at == t1
    assert state.last_communication_at == t2
    assert state.contact_count == 2


def test_delta_conversion_time_on_terminal_phase():
    state = PcpCommunicationState()
    t1 = datetime(2026, 7, 4, 10, 0, 0)
    t2 = datetime(2026, 7, 13, 10, 0, 0)
    state.record_contact(t1)
    state.record_contact(t2)
    state.current_phase = CommunicationPhase.SIGNED
    state.update_delta_conversion_time()
    assert state.delta_conversion_time == timedelta(days=9)

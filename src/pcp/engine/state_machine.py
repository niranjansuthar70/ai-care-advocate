from __future__ import annotations

from src.pcp.engine.models import (
    CommunicationPhase,
    PcpCommunicationState,
    PcpTranscriptAnalysis,
    VerificationChecklist,
)


def is_order_rejected(
    analysis: PcpTranscriptAnalysis,
    verification: VerificationChecklist,
    *,
    expected_code: str,
) -> bool:
    if verification.rejection_detected:
        return True
    if analysis.rejection_reason:
        return True
    if analysis.billing_code is not None and analysis.billing_code != expected_code:
        return True
    return False


def _verification_complete(verification: VerificationChecklist) -> bool:
    return (
        verification.patient_details_confirmed
        and verification.order_details_confirmed
        and verification.followup_scheduled
        and verification.closing_attempted
    )


def next_phase_after_call(
    current: CommunicationPhase,
    analysis: PcpTranscriptAnalysis,
    verification: VerificationChecklist,
    *,
    expected_code: str,
    contact_limit_reached: bool = False,
) -> CommunicationPhase:
    """Determine phase after processing a call transcript."""
    if current in (CommunicationPhase.CLOSED, CommunicationPhase.INFORM_PATIENT):
        return current

    if analysis.order_signed:
        return CommunicationPhase.SIGNED

    if is_order_rejected(analysis, verification, expected_code=expected_code):
        return CommunicationPhase.REJECTED

    if contact_limit_reached:
        return CommunicationPhase.REJECTED

    if analysis.no_answer or analysis.order_in_queue:
        return CommunicationPhase.FOLLOWUP

    if _verification_complete(verification) and not analysis.order_signed:
        return CommunicationPhase.FOLLOWUP

    if current == CommunicationPhase.VERIFICATION:
        return CommunicationPhase.VERIFICATION

    if current == CommunicationPhase.FOLLOWUP:
        return CommunicationPhase.FOLLOWUP

    if current in (CommunicationPhase.SIGNED, CommunicationPhase.REJECTED):
        return CommunicationPhase.INFORM_PATIENT

    return current


def next_phase_after_outcome(current: CommunicationPhase) -> CommunicationPhase:
    """Auto-advance signed/rejected cases toward patient notification."""
    if current == CommunicationPhase.SIGNED:
        return CommunicationPhase.INFORM_PATIENT
    if current == CommunicationPhase.REJECTED:
        return CommunicationPhase.INFORM_PATIENT
    return current


def next_phase_after_patient_informed(current: CommunicationPhase) -> CommunicationPhase:
    if current == CommunicationPhase.INFORM_PATIENT:
        return CommunicationPhase.CLOSED
    return current


def apply_phase_to_state(
    state: PcpCommunicationState,
    new_phase: CommunicationPhase,
) -> None:
    state.current_phase = new_phase
    state.current_status = derive_current_status(new_phase, state.verification, state.order_signed)
    if new_phase == CommunicationPhase.SIGNED:
        state.order_signed = True
    state.update_delta_conversion_time()


def derive_current_status(
    phase: CommunicationPhase,
    verification: VerificationChecklist,
    order_signed: bool,
) -> str:
    if phase == CommunicationPhase.VERIFICATION:
        missing = []
        if not verification.patient_details_confirmed:
            missing.append("patient details")
        if not verification.order_details_confirmed:
            missing.append("order details")
        if not verification.followup_scheduled:
            missing.append("followup")
        if not verification.closing_attempted:
            missing.append("closing")
        if missing:
            return f"verifying: pending {', '.join(missing)}"
        return "verification complete, awaiting order"

    if phase == CommunicationPhase.FOLLOWUP:
        return "following up with PCP for written order"

    if phase == CommunicationPhase.SIGNED or order_signed:
        return "written order signed"

    if phase == CommunicationPhase.REJECTED:
        return "order rejected or unreachable"

    if phase == CommunicationPhase.INFORM_PATIENT:
        return "informing patient of outcome"

    if phase == CommunicationPhase.CLOSED:
        return "closed"

    return "awaiting_first_call"

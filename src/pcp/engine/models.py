from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
DEFAULT_STATE_PATH = DEFAULT_OUTPUT_DIR / "pcp_communication_state.json"
DEFAULT_EVENTS_PATH = DEFAULT_OUTPUT_DIR / "pcp_events.jsonl"
DEFAULT_RECORDINGS_PATH = DEFAULT_OUTPUT_DIR / "pcp_call_recordings.csv"


class ContactStatus(str, Enum):
    NOT_CONTACTED = "not_contacted"
    CONTACTED = "contacted"


class CommunicationPhase(str, Enum):
    VERIFICATION = "verification"
    FOLLOWUP = "followup"
    SIGNED = "signed"
    REJECTED = "rejected"
    INFORM_PATIENT = "inform_patient"
    CLOSED = "closed"


class PcpAction(str, Enum):
    VERIFY_PATIENT = "verify_patient"
    VERIFY_ORDER = "verify_order"
    SCHEDULE_FOLLOWUP = "schedule_followup"
    NUDGE = "nudge"
    RETRY = "retry"
    INFORM_PATIENT = "inform_patient"
    CLOSE_SIGNED = "close_signed"
    CLOSE_REJECTED = "close_rejected"
    GIVE_UP = "give_up"
    COMPLETE = "complete"


class VerificationChecklist(BaseModel):
    patient_details_confirmed: bool = False
    order_details_confirmed: bool = False
    followup_scheduled: bool = False
    closing_attempted: bool = False
    rejection_detected: bool = False

    def merge(self, other: VerificationChecklist) -> VerificationChecklist:
        """Cumulative merge — once confirmed, stays confirmed."""
        return VerificationChecklist(
            patient_details_confirmed=self.patient_details_confirmed or other.patient_details_confirmed,
            order_details_confirmed=self.order_details_confirmed or other.order_details_confirmed,
            followup_scheduled=self.followup_scheduled or other.followup_scheduled,
            closing_attempted=self.closing_attempted or other.closing_attempted,
            rejection_detected=self.rejection_detected or other.rejection_detected,
        )


class PcpTranscriptAnalysis(BaseModel):
    no_answer: bool = False
    verbal_order_noted: bool = False
    written_order_submitted: bool = False
    order_in_queue: bool = False
    billing_code: str | None = None
    order_signed: bool = False
    rejection_reason: str | None = None
    summary: str = ""


def derive_order_signed(
    *,
    written_order_submitted: bool,
    billing_code: str | None,
    expected_code: str,
) -> bool:
    return written_order_submitted and billing_code == expected_code


class PcpCallEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    contact_number: int
    occurred_at: datetime
    transcription_text: str
    days_since_last_contact: int
    analysis: PcpTranscriptAnalysis
    verification: VerificationChecklist
    action_taken: PcpAction
    phase_before: CommunicationPhase
    phase_after: CommunicationPhase


class PcpCommunicationState(BaseModel):
    contact_status: ContactStatus = ContactStatus.NOT_CONTACTED
    contacted_at: datetime | None = None
    last_communication_at: datetime | None = None
    current_phase: CommunicationPhase = CommunicationPhase.VERIFICATION
    current_status: str = "awaiting_first_call"
    contact_count: int = 0
    order_signed: bool = False
    patient_informed: bool = False
    delta_conversion_time: timedelta | None = None
    verification: VerificationChecklist = Field(default_factory=VerificationChecklist)

    def record_contact(self, occurred_at: datetime) -> None:
        """Update contact timestamps on each call event."""
        self.contact_count += 1
        self.last_communication_at = occurred_at
        if self.contact_status == ContactStatus.NOT_CONTACTED:
            self.contact_status = ContactStatus.CONTACTED
            self.contacted_at = occurred_at

    def update_delta_conversion_time(self) -> None:
        """Set delta when reaching a terminal conversion phase."""
        if self.contacted_at is None or self.last_communication_at is None:
            return
        if self.current_phase in (
            CommunicationPhase.SIGNED,
            CommunicationPhase.REJECTED,
            CommunicationPhase.INFORM_PATIENT,
            CommunicationPhase.CLOSED,
        ):
            self.delta_conversion_time = self.last_communication_at - self.contacted_at

    @property
    def is_terminal(self) -> bool:
        return self.current_phase in (
            CommunicationPhase.CLOSED,
            CommunicationPhase.INFORM_PATIENT,
        )

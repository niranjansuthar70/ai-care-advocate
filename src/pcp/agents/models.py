from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from src.pcp.engine.models import (
    CommunicationPhase,
    ContactStatus,
    PcpAction,
    PcpCallEvent,
    PcpCommunicationState,
    PcpTranscriptAnalysis,
    VerificationChecklist,
)


class PatientLoopUpdate(BaseModel):
    should_inform_patient: bool = False
    patient_status_summary: str = ""
    patient_message_draft: str | None = None
    waiting_on: Literal["pcp", "supplier", "medicare"] = "pcp"


class StateUpdate(BaseModel):
    current_phase: CommunicationPhase
    current_status: str
    order_signed: bool = False
    patient_informed: bool = False
    contact_status: ContactStatus = ContactStatus.CONTACTED


class PcpAgentDecision(BaseModel):
    """One agent turn output — one call event."""

    analysis: PcpTranscriptAnalysis
    verification: VerificationChecklist
    state_update: StateUpdate
    patient_loop: PatientLoopUpdate
    next_action: PcpAction
    phase_before: CommunicationPhase
    phase_after: CommunicationPhase
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class AgentTurnResult(BaseModel):
    decision: PcpAgentDecision
    event: PcpCallEvent
    state: PcpCommunicationState
    patient_loop: PatientLoopUpdate

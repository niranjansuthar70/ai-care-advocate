from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from src.pcp.agents.models import AgentTurnResult, PcpAgentDecision
from src.pcp.engine.models import PcpCallEvent, PcpCommunicationState
from src.pcp.engine.state_machine import apply_phase_to_state


def load_decision(path: Path) -> PcpAgentDecision:
    data = json.loads(path.read_text(encoding="utf-8"))
    return PcpAgentDecision.model_validate(data)


def load_state(path: Path | None) -> PcpCommunicationState:
    if path is None or not path.exists():
        return PcpCommunicationState()
    data = json.loads(path.read_text(encoding="utf-8"))
    return PcpCommunicationState.model_validate(data)


def apply_agent_decision(
    *,
    decision: PcpAgentDecision,
    transcript: str,
    state: PcpCommunicationState | None = None,
    days_since_last_contact: int = 0,
    occurred_at: datetime | None = None,
    start_time: datetime | None = None,
) -> AgentTurnResult:
    """Apply one agent decision — mirrors one engine process_transcript turn."""
    state = state or PcpCommunicationState()
    phase_before = state.current_phase

    if occurred_at is None:
        occurred_at = _next_timestamp(
            state,
            days_since_last_contact,
            start_time or datetime(2026, 7, 4, 10, 0, 0),
        )

    state.record_contact(occurred_at)
    state.verification = state.verification.merge(decision.verification)

    update = decision.state_update
    apply_phase_to_state(state, update.current_phase)
    state.current_status = update.current_status
    state.order_signed = update.order_signed
    state.patient_informed = update.patient_informed
    state.contact_status = update.contact_status
    state.update_delta_conversion_time()

    event = PcpCallEvent(
        contact_number=state.contact_count,
        occurred_at=occurred_at,
        transcription_text=transcript,
        days_since_last_contact=days_since_last_contact,
        analysis=decision.analysis,
        verification=state.verification.model_copy(),
        action_taken=decision.next_action,
        phase_before=decision.phase_before if decision.phase_before else phase_before,
        phase_after=decision.phase_after if decision.phase_after else state.current_phase,
    )

    return AgentTurnResult(
        decision=decision,
        event=event,
        state=state,
        patient_loop=decision.patient_loop,
    )


def _next_timestamp(
    state: PcpCommunicationState,
    days_since_last: int,
    start_time: datetime,
) -> datetime:
    if state.contact_count == 0:
        return start_time
    if state.last_communication_at is None:
        return start_time
    if days_since_last == 0:
        return state.last_communication_at
    return state.last_communication_at + timedelta(days=days_since_last)

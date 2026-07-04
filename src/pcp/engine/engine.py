from __future__ import annotations

from datetime import datetime, timedelta

from src.pcp.analyzers.base import TranscriptAnalyzer
from src.pcp.analyzers.scripted import ScriptedTranscriptAnalyzer
from src.pcp.engine.actions import ActionDecider, is_terminal_action
from src.pcp.engine.models import CommunicationPhase, PcpCallEvent, PcpCommunicationState
from src.pcp.engine.state_machine import (
    apply_phase_to_state,
    next_phase_after_call,
    next_phase_after_outcome,
    next_phase_after_patient_informed,
)
from src.pcp.generators.base import CallGenerator
from src.shared.models import PatientContext, PcpContext


class PcpCommunicationEngine:
    def __init__(
        self,
        *,
        patient: PatientContext | None = None,
        pcp: PcpContext | None = None,
        analyzer: TranscriptAnalyzer | None = None,
        decider: ActionDecider | None = None,
        max_contacts: int = 10,
        rng_seed: int = 42,
        start_time: datetime | None = None,
    ) -> None:
        self.patient = patient or PatientContext()
        self.pcp = pcp or PcpContext()
        self.analyzer = analyzer or ScriptedTranscriptAnalyzer()
        self.max_contacts = max_contacts
        self.decider = decider or ActionDecider(max_contacts=max_contacts, rng_seed=rng_seed)
        self.state = PcpCommunicationState()
        self.events: list[PcpCallEvent] = []
        self._simulated_now = start_time or datetime(2026, 7, 4, 10, 0, 0)
        self._last_contact_at: datetime | None = None

    def process_transcript(self, text: str, *, days_since_last: int = 0) -> PcpCallEvent:
        phase_before = self.state.current_phase
        occurred_at = self._next_timestamp(days_since_last)
        self.state.record_contact(occurred_at)
        self._last_contact_at = occurred_at

        result = self.analyzer.extract(text, pcp=self.pcp, patient=self.patient)
        self.state.verification = self.state.verification.merge(result.verification)

        contact_limit_reached = self.state.contact_count >= self.max_contacts
        new_phase = next_phase_after_call(
            phase_before,
            result.analysis,
            self.state.verification,
            expected_code=self.patient.equipment_code,
            contact_limit_reached=contact_limit_reached,
        )
        apply_phase_to_state(self.state, new_phase)

        action = self.decider.decide(
            self.state,
            result.analysis,
            self.state.verification,
        )

        event = PcpCallEvent(
            contact_number=self.state.contact_count,
            occurred_at=occurred_at,
            transcription_text=text,
            days_since_last_contact=days_since_last,
            analysis=result.analysis,
            verification=self.state.verification.model_copy(),
            action_taken=action,
            phase_before=phase_before,
            phase_after=self.state.current_phase,
        )
        self.events.append(event)
        return event

    def finalize_outcome(self) -> None:
        """Mock patient notification after PCP chase ends."""
        if self.state.current_phase == CommunicationPhase.SIGNED:
            apply_phase_to_state(
                self.state,
                next_phase_after_outcome(CommunicationPhase.SIGNED),
            )
            self.state.patient_informed = True
            apply_phase_to_state(
                self.state,
                next_phase_after_patient_informed(CommunicationPhase.INFORM_PATIENT),
            )
        elif self.state.current_phase == CommunicationPhase.REJECTED:
            apply_phase_to_state(
                self.state,
                next_phase_after_outcome(CommunicationPhase.REJECTED),
            )
            self.state.patient_informed = True
            apply_phase_to_state(
                self.state,
                next_phase_after_patient_informed(CommunicationPhase.INFORM_PATIENT),
            )

    def run_until_terminal(
        self,
        initial_transcript: str,
        *,
        generator: CallGenerator | None = None,
    ) -> PcpCommunicationState:
        event = self.process_transcript(initial_transcript, days_since_last=0)
        while (
            not is_terminal_action(event.action_taken)
            and self.state.contact_count < self.max_contacts
        ):
            if generator is None:
                break
            days_since_last, text = generator.next_call(
                state=self.state,
                action=event.action_taken,
            )
            event = self.process_transcript(text, days_since_last=days_since_last)

        self.finalize_outcome()
        return self.state

    def _next_timestamp(self, days_since_last: int) -> datetime:
        if self._last_contact_at is None:
            return self._simulated_now
        if days_since_last == 0:
            return self._last_contact_at
        return self._last_contact_at + timedelta(days=days_since_last)

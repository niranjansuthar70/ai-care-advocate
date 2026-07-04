from datetime import timedelta
from pathlib import Path

import pytest

from src.pcp.engine.actions import ActionDecider
from src.pcp.engine.engine import PcpCommunicationEngine
from src.pcp.engine.models import CommunicationPhase, ContactStatus, PcpAction
from src.pcp.generators.base import TranscriptListGenerator

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"
INITIAL_TRANSCRIPT = FIXTURES / "pcp_initial.txt"

SIGNED_TRANSCRIPT = (
    "Front desk: Dr. Chen signed the K0001 manual wheelchair order today "
    "and submitted it to the DME supplier."
)
QUEUE_TRANSCRIPT = (
    "Front desk: The written order is still in the MA queue waiting for Dr. Chen."
)


def test_process_initial_transcript_updates_state():
    engine = PcpCommunicationEngine(
        decider=ActionDecider(weights={"followup": {"nudge": 1.0, "schedule_followup": 0.0}, "no_answer": {}}),
    )
    text = INITIAL_TRANSCRIPT.read_text(encoding="utf-8")
    event = engine.process_transcript(text)

    assert event.contact_number == 1
    assert event.action_taken == PcpAction.NUDGE
    assert engine.state.contact_status == ContactStatus.CONTACTED
    assert engine.state.contacted_at is not None
    assert engine.state.current_phase == CommunicationPhase.FOLLOWUP
    assert engine.state.verification.patient_details_confirmed
    assert len(engine.events) == 1


def test_run_until_terminal_reaches_signed_and_closed():
    engine = PcpCommunicationEngine(
        decider=ActionDecider(weights={"followup": {"nudge": 1.0, "schedule_followup": 0.0}, "no_answer": {}}),
    )
    generator = TranscriptListGenerator([
        (3, QUEUE_TRANSCRIPT),
        (2, SIGNED_TRANSCRIPT),
    ])
    state = engine.run_until_terminal(
        INITIAL_TRANSCRIPT.read_text(encoding="utf-8"),
        generator=generator,
    )

    assert state.order_signed
    assert state.current_phase == CommunicationPhase.CLOSED
    assert state.patient_informed
    assert len(engine.events) == 3
    assert engine.events[-1].action_taken == PcpAction.CLOSE_SIGNED
    assert state.delta_conversion_time == timedelta(days=5)


def test_run_without_generator_stops_after_initial():
    engine = PcpCommunicationEngine(
        decider=ActionDecider(weights={"followup": {"nudge": 1.0, "schedule_followup": 0.0}, "no_answer": {}}),
    )
    state = engine.run_until_terminal(INITIAL_TRANSCRIPT.read_text(encoding="utf-8"))

    assert len(engine.events) == 1
    assert state.current_phase == CommunicationPhase.FOLLOWUP
    assert not state.patient_informed


def test_give_up_on_max_contacts():
    engine = PcpCommunicationEngine(
        max_contacts=2,
        decider=ActionDecider(
            max_contacts=2,
            weights={"followup": {"nudge": 1.0, "schedule_followup": 0.0}, "no_answer": {}},
        ),
    )
    generator = TranscriptListGenerator([(1, QUEUE_TRANSCRIPT)])
    state = engine.run_until_terminal(
        INITIAL_TRANSCRIPT.read_text(encoding="utf-8"),
        generator=generator,
    )

    assert state.current_phase == CommunicationPhase.CLOSED
    assert state.patient_informed
    assert engine.events[-1].action_taken == PcpAction.GIVE_UP

import random
from pathlib import Path

from src.pcp.engine.actions import ActionDecider
from src.pcp.engine.engine import PcpCommunicationEngine
from src.pcp.engine.models import CommunicationPhase, PcpAction
from src.pcp.generators.stochastic import (
    StochasticCallGenerator,
    load_outcome_pool,
    load_transcripts,
    pick_weighted_outcome,
)

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"
INITIAL_TRANSCRIPT = FIXTURES / "pcp_initial.txt"


def test_load_fixtures():
    pool = load_outcome_pool()
    transcripts = load_transcripts()
    assert "nudge" in pool
    assert "signed" in transcripts


def test_pick_weighted_outcome_deterministic():
    outcomes = [
        {"weight": 0.4, "days_since_last": 3, "transcript_key": "in_queue"},
        {"weight": 0.6, "days_since_last": 1, "transcript_key": "signed"},
    ]
    rng1 = random.Random(42 + 2)
    rng2 = random.Random(42 + 2)
    assert pick_weighted_outcome(rng1, outcomes) == pick_weighted_outcome(rng2, outcomes)


def test_next_call_resolves_transcript_for_action():
    generator = StochasticCallGenerator(
        rng_seed=42,
        outcome_pool={"nudge": [{"weight": 1.0, "days_since_last": 1, "transcript_key": "signed"}]},
        transcripts={"signed": "Dr. Chen signed the K0001 order today."},
    )
    from src.pcp.engine.models import PcpCommunicationState

    state = PcpCommunicationState(contact_count=2)
    days, text = generator.next_call(state=state, action=PcpAction.NUDGE)
    assert days == 1
    assert "K0001" in text


def test_next_call_falls_back_to_nudge_pool():
    generator = StochasticCallGenerator(
        rng_seed=42,
        outcome_pool={"nudge": [{"weight": 1.0, "days_since_last": 2, "transcript_key": "in_queue"}]},
        transcripts=load_transcripts(),
    )
    from src.pcp.engine.models import PcpCommunicationState

    state = PcpCommunicationState(contact_count=1)
    days, text = generator.next_call(state=state, action=PcpAction.INFORM_PATIENT)
    assert days == 2
    assert "queue" in text.lower()


def test_stochastic_run_is_reproducible_with_seed():
    def run_once() -> list[str]:
        engine = PcpCommunicationEngine(
            rng_seed=0,
            decider=ActionDecider(
                rng_seed=0,
                weights={"followup": {"nudge": 1.0, "schedule_followup": 0.0}, "no_answer": {"retry": 1.0, "nudge": 0.0}},
            ),
        )
        generator = StochasticCallGenerator(rng_seed=0)
        engine.run_until_terminal(
            INITIAL_TRANSCRIPT.read_text(encoding="utf-8"),
            generator=generator,
        )
        return [event.transcription_text for event in engine.events]

    assert run_once() == run_once()


def test_stochastic_run_reaches_signed_with_seed_0():
    engine = PcpCommunicationEngine(
        rng_seed=0,
        decider=ActionDecider(
            rng_seed=0,
            weights={"followup": {"nudge": 1.0, "schedule_followup": 0.0}, "no_answer": {"retry": 1.0, "nudge": 0.0}},
        ),
    )
    generator = StochasticCallGenerator(rng_seed=0)
    state = engine.run_until_terminal(
        INITIAL_TRANSCRIPT.read_text(encoding="utf-8"),
        generator=generator,
    )

    assert state.order_signed
    assert state.current_phase == CommunicationPhase.CLOSED
    assert state.patient_informed
    assert len(engine.events) >= 2
    assert engine.events[-1].action_taken == PcpAction.CLOSE_SIGNED


def test_stochastic_run_can_timeout_with_seed_42():
    engine = PcpCommunicationEngine(
        rng_seed=42,
        decider=ActionDecider(
            rng_seed=42,
            weights={"followup": {"nudge": 1.0, "schedule_followup": 0.0}, "no_answer": {"retry": 1.0, "nudge": 0.0}},
        ),
    )
    generator = StochasticCallGenerator(rng_seed=42)
    state = engine.run_until_terminal(
        INITIAL_TRANSCRIPT.read_text(encoding="utf-8"),
        generator=generator,
    )

    assert not state.order_signed
    assert state.current_phase == CommunicationPhase.CLOSED
    assert engine.events[-1].action_taken == PcpAction.GIVE_UP

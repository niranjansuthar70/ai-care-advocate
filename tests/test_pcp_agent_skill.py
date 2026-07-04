import json
from pathlib import Path

import pytest

from src.pcp.agents.apply import apply_agent_decision, load_decision, load_state
from src.pcp.agents.models import PcpAgentDecision
from src.pcp.engine.actions import ActionDecider
from src.pcp.engine.engine import PcpCommunicationEngine
from src.pcp.engine.models import CommunicationPhase, PcpAction

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"
GOLDEN = FIXTURES / "agent_golden"
INITIAL = FIXTURES / "pcp_initial.txt"


def test_golden_decision_files_validate():
    for name in ("turn1_decision.json", "turn2_decision.json"):
        decision = load_decision(GOLDEN / name)
        assert isinstance(decision, PcpAgentDecision)
        assert 0 <= decision.confidence <= 1


def test_apply_turn1_matches_scripted_engine():
    transcript = INITIAL.read_text(encoding="utf-8")
    prior = load_state(GOLDEN / "turn1_prior_state.json")
    decision = load_decision(GOLDEN / "turn1_decision.json")

    agent_result = apply_agent_decision(
        decision=decision,
        transcript=transcript,
        state=prior,
    )

    engine = PcpCommunicationEngine(
        decider=ActionDecider(weights={"followup": {"nudge": 1.0, "schedule_followup": 0.0}, "no_answer": {}}),
    )
    event = engine.process_transcript(transcript)

    assert agent_result.event.action_taken == event.action_taken == PcpAction.NUDGE
    assert agent_result.state.current_phase == CommunicationPhase.FOLLOWUP
    assert agent_result.state.verification.patient_details_confirmed
    assert not agent_result.patient_loop.should_inform_patient


def test_apply_turn2_chain():
    transcript1 = INITIAL.read_text(encoding="utf-8")
    transcript2 = "Front desk: The written order is still in the MA queue waiting for Dr. Chen."

    turn1 = apply_agent_decision(
        decision=load_decision(GOLDEN / "turn1_decision.json"),
        transcript=transcript1,
        state=load_state(GOLDEN / "turn1_prior_state.json"),
    )
    turn2 = apply_agent_decision(
        decision=load_decision(GOLDEN / "turn2_decision.json"),
        transcript=transcript2,
        state=turn1.state,
        days_since_last_contact=3,
    )

    assert turn2.state.contact_count == 2
    assert turn2.state.current_phase == CommunicationPhase.FOLLOWUP
    assert turn2.event.action_taken == PcpAction.NUDGE
    assert turn2.state.verification.patient_details_confirmed


def test_cli_agent_validate_and_apply(tmp_path, capsys):
    from src.pcp.cli import main

    rc = main(["agent-validate", "--decision-file", str(GOLDEN / "turn1_decision.json")])
    assert rc == 0
    assert "[valid]" in capsys.readouterr().out

    rc = main([
        "agent-apply",
        "--decision-file", str(GOLDEN / "turn1_decision.json"),
        "--transcript-file", str(INITIAL),
        "--state-file", str(GOLDEN / "turn1_prior_state.json"),
        "--output-dir", str(tmp_path / "out"),
    ])
    assert rc == 0
    assert (tmp_path / "out" / "pcp_communication_state.json").exists()
    state = json.loads((tmp_path / "out" / "pcp_communication_state.json").read_text(encoding="utf-8"))
    assert state["current_phase"] == "followup"

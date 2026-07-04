import json
from datetime import datetime
from pathlib import Path

from src.pcp.engine.models import (
    CommunicationPhase,
    ContactStatus,
    PcpAction,
    PcpCallEvent,
    PcpCommunicationState,
    PcpTranscriptAnalysis,
    VerificationChecklist,
)
from src.pcp.persistence import persist_engine_run, write_events, write_recordings_csv, write_state


def test_write_state_serializes_timestamps(tmp_path):
    state = PcpCommunicationState(
        contact_status=ContactStatus.CONTACTED,
        contacted_at=datetime(2026, 7, 4, 10, 0, 0),
        current_phase=CommunicationPhase.FOLLOWUP,
    )
    path = tmp_path / "state.json"
    write_state(state, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["contact_status"] == "contacted"
    assert data["current_phase"] == "followup"


def test_persist_engine_run_writes_all_artifacts(tmp_path):
    state = PcpCommunicationState(contact_count=1, current_phase=CommunicationPhase.FOLLOWUP)
    event = PcpCallEvent(
        contact_number=1,
        occurred_at=datetime(2026, 7, 4, 10, 0, 0),
        transcription_text="Test transcript",
        days_since_last_contact=0,
        analysis=PcpTranscriptAnalysis(summary="test"),
        verification=VerificationChecklist(patient_details_confirmed=True),
        action_taken=PcpAction.NUDGE,
        phase_before=CommunicationPhase.VERIFICATION,
        phase_after=CommunicationPhase.FOLLOWUP,
    )
    paths = persist_engine_run(state=state, events=[event], output_dir=tmp_path)

    assert paths["state"].exists()
    assert paths["events"].exists()
    assert paths["recordings"].exists()
    assert "Test transcript" in paths["recordings"].read_text(encoding="utf-8")


def test_cli_process(tmp_path, capsys):
    from src.pcp.cli import main

    transcript = tmp_path / "call.txt"
    transcript.write_text(
        "Front desk: Verbal order noted in chart. Written K0001 order not yet submitted. In MA queue.",
        encoding="utf-8",
    )
    rc = main([
        "process",
        "--transcript-file", str(transcript),
        "--output-dir", str(tmp_path / "out"),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[event 1]" in out
    assert (tmp_path / "out" / "pcp_communication_state.json").exists()


def test_cli_run(tmp_path, capsys):
    from src.pcp.cli import main

    initial = tmp_path / "initial.txt"
    initial.write_text(
        Path("data/fixtures/pcp_initial.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    rc = main([
        "run",
        "--transcript-file", str(initial),
        "--seed", "0",
        "--output-dir", str(tmp_path / "out"),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[result]" in out
    assert (tmp_path / "out" / "pcp_events.jsonl").exists()

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.pcp.engine.models import (
    DEFAULT_EVENTS_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RECORDINGS_PATH,
    DEFAULT_STATE_PATH,
    PcpCallEvent,
    PcpCommunicationState,
)


def output_paths(output_dir: Path | None = None) -> tuple[Path, Path, Path]:
    base = output_dir or DEFAULT_OUTPUT_DIR
    return (
        base / "pcp_communication_state.json",
        base / "pcp_events.jsonl",
        base / "pcp_call_recordings.csv",
    )


def write_state(state: PcpCommunicationState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )


def write_events(events: list[PcpCallEvent], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(event.model_dump(mode="json")) for event in events]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_recordings_csv(events: list[PcpCallEvent], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "contact_number",
        "occurred_at",
        "days_since_last_contact",
        "phase_before",
        "phase_after",
        "action_taken",
        "order_signed",
        "transcription_text",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for event in events:
            writer.writerow(
                {
                    "contact_number": event.contact_number,
                    "occurred_at": event.occurred_at.isoformat(),
                    "days_since_last_contact": event.days_since_last_contact,
                    "phase_before": event.phase_before.value,
                    "phase_after": event.phase_after.value,
                    "action_taken": event.action_taken.value,
                    "order_signed": event.analysis.order_signed,
                    "transcription_text": event.transcription_text,
                }
            )


def persist_engine_run(
    *,
    state: PcpCommunicationState,
    events: list[PcpCallEvent],
    output_dir: Path | None = None,
) -> dict[str, Path]:
    state_path, events_path, recordings_path = output_paths(output_dir)
    write_state(state, state_path)
    write_events(events, events_path)
    write_recordings_csv(events, recordings_path)
    return {
        "state": state_path,
        "events": events_path,
        "recordings": recordings_path,
    }

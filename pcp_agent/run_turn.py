from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from pcp_agent.graph import run_turn
from pcp_agent.persistence import (
    case_state_from_graph,
    load_state_file,
    load_state_json,
    save_state_json,
)
from pcp_agent.state import PCPCaseState, new_case

ELEANOR_DEFAULTS = dict(
    patient_id="eleanor-martinez",
    equipment="standard manual wheelchair",
    billing_code="K0001",
    pcp_name="Dr. Sarah Chen",
    pcp_phone="312-555-0142",
)

DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"


def _print_section(title: str, payload: Any) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, indent=2))


def _resolve_state(state_file: str | None, patient_id: str) -> PCPCaseState:
    if state_file:
        return load_state_file(state_file)
    saved = load_state_json(patient_id)
    if saved:
        return saved
    return new_case(**ELEANOR_DEFAULTS)


def _load_transcript(path: str | None, inline: str | None) -> str:
    if inline is not None:
        return inline
    if not path:
        raise ValueError("A transcript is required via --transcript-file or --transcript")
    return Path(path).read_text(encoding="utf-8")


def _run_once(
    state: PCPCaseState,
    transcript: str,
    *,
    model: str | None,
) -> PCPCaseState:
    _print_section("BEFORE STATE", state)
    print("\n--- transcript ---")
    print(transcript)

    graph_result = run_turn(state, transcript, model=model)
    after_state = case_state_from_graph(graph_result)

    extract_diff = graph_result.get("extract_diff")
    if extract_diff:
        _print_section("EXTRACT DIFF", extract_diff)

    _print_section("AFTER STATE", after_state)
    _print_section("DECISION", {"next_action": after_state["next_action"]})

    if after_state.get("patient_message_draft"):
        _print_section("PATIENT MESSAGE", {"draft": after_state["patient_message_draft"]})

    saved_path = save_state_json(after_state)
    print(f"\nState saved to {saved_path}")
    print("Checkpoint saved to LangGraph MemorySaver (thread_id={})".format(after_state["patient_id"]))

    return after_state


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Run one PCP agent turn: extract → merge → decide → contact/followup."
    )
    parser.add_argument("--transcript-file", help="Path to call transcript text file.")
    parser.add_argument("--transcript", help="Inline transcript text.")
    parser.add_argument("--state-file", help="Prior PCPCaseState JSON.")
    parser.add_argument("--patient-id", default=ELEANOR_DEFAULTS["patient_id"])
    parser.add_argument(
        "--model",
        default=os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL),
        help=f"Groq model id (default: {DEFAULT_GROQ_MODEL}).",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="After a followup decision, prompt for the next transcript file.",
    )
    args = parser.parse_args(argv)

    try:
        if args.interactive:
            state = _resolve_state(args.state_file, args.patient_id)
            while True:
                transcript_path = input(
                    "\nTranscript file path (or 'q' to quit): "
                ).strip()
                if transcript_path.lower() in {"q", "quit", "exit"}:
                    break
                if not Path(transcript_path).exists():
                    print(f"File not found: {transcript_path}")
                    continue
                transcript = Path(transcript_path).read_text(encoding="utf-8")
                state = _run_once(state, transcript, model=args.model)
                if state["next_action"] != "followup":
                    print("\nTerminal decision reached. Exiting interactive loop.")
                    break
                print("\nDecision is followup — provide the next transcript when ready.")
            return 0

        transcript = _load_transcript(args.transcript_file, args.transcript)
        state = _resolve_state(args.state_file, args.patient_id)
        after_state = _run_once(state, transcript, model=args.model)

        if after_state["next_action"] == "followup":
            print(
                "\nNext step: run again with the next transcript file when ready, e.g.\n"
                "  python -m pcp_agent.run_turn --transcript-file data/fixtures/extract/turn2_order_in_progress.txt"
            )
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

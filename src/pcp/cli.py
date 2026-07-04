from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.pcp.engine.actions import ActionDecider
from src.pcp.engine.engine import PcpCommunicationEngine
from src.pcp.engine.models import PcpCallEvent
from src.pcp.generators.stochastic import StochasticCallGenerator
from src.pcp.persistence import persist_engine_run

DEFAULT_INITIAL = Path("data/fixtures/pcp_initial.txt")


def _load_transcript(*, transcript: str | None, transcript_file: Path | None) -> str:
    if transcript_file is not None:
        return transcript_file.read_text(encoding="utf-8")
    if transcript is not None:
        return transcript
    raise ValueError("Provide --transcript-file or --transcript")


def _check_mark(value: bool) -> str:
    return "Y" if value else "N"


def _format_delta(state) -> str:
    if state.delta_conversion_time is None:
        return "-"
    days = state.delta_conversion_time.days
    return f"{days} days"


def print_event(event: PcpCallEvent, *, state) -> None:
    v = event.verification
    print(
        f"[event {event.contact_number}] "
        f"phase {event.phase_before.value} -> {event.phase_after.value} | "
        f"action {event.action_taken.value}"
    )
    print(
        "  verification: "
        f"patient={_check_mark(v.patient_details_confirmed)} "
        f"order={_check_mark(v.order_details_confirmed)} "
        f"followup={_check_mark(v.followup_scheduled)} "
        f"closing={_check_mark(v.closing_attempted)}"
    )
    print(
        f"  contacted_at={state.contacted_at.isoformat() if state.contacted_at else '-'} | "
        f"delta_conversion_time={_format_delta(state)}"
    )
    if event.analysis.order_signed:
        print(f"  order_signed=True | summary={event.analysis.summary}")


def cmd_process(args: argparse.Namespace) -> int:
    text = _load_transcript(transcript=args.transcript, transcript_file=args.transcript_file)
    engine = PcpCommunicationEngine(
        max_contacts=args.max_contacts,
        rng_seed=args.seed,
        decider=ActionDecider(max_contacts=args.max_contacts, rng_seed=args.seed),
    )
    event = engine.process_transcript(text)
    print_event(event, state=engine.state)

    paths = persist_engine_run(
        state=engine.state,
        events=engine.events,
        output_dir=args.output_dir,
    )
    print(f"[saved] state={paths['state']}")
    print(f"[saved] events={paths['events']}")
    print(f"[saved] recordings={paths['recordings']}")

    if args.json:
        print(json.dumps(engine.state.model_dump(mode="json"), indent=2))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    text = _load_transcript(transcript=args.transcript, transcript_file=args.transcript_file)
    decider = ActionDecider(max_contacts=args.max_contacts, rng_seed=args.seed)
    engine = PcpCommunicationEngine(
        max_contacts=args.max_contacts,
        rng_seed=args.seed,
        decider=decider,
    )
    generator = StochasticCallGenerator(rng_seed=args.seed)
    state = engine.run_until_terminal(text, generator=generator)

    for event in engine.events:
        print_event(event, state=engine.state)

    print(
        f"[result] contacts={state.contact_count} "
        f"phase={state.current_phase.value} "
        f"order_signed={state.order_signed} "
        f"delta_conversion_time={_format_delta(state)}"
    )

    paths = persist_engine_run(
        state=state,
        events=engine.events,
        output_dir=args.output_dir,
    )
    print(f"[saved] state={paths['state']}")
    print(f"[saved] events={paths['events']}")
    print(f"[saved] recordings={paths['recordings']}")

    if args.json:
        print(json.dumps(state.model_dump(mode="json"), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PCP communication engine demo")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--transcript-file", type=Path, default=DEFAULT_INITIAL)
    common.add_argument("--transcript", type=str)
    common.add_argument("--seed", type=int, default=10)
    common.add_argument("--max-contacts", type=int, default=10)
    common.add_argument("--output-dir", type=Path)
    common.add_argument("--json", action="store_true")

    sub.add_parser("process", parents=[common], help="Process a single call transcript")
    sub.add_parser("run", parents=[common], help="Run until terminal with stochastic follow-ups")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "process":
        return cmd_process(args)
    if args.command == "run":
        return cmd_run(args)
    parser.error(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import os
import sys
from enum import Enum
from typing import Any

from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel, Field

from pcp_agent.state import PCPCaseState

DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"


class ExtractSignal(str, Enum):
    ACKNOWLEDGED = "acknowledged"
    STALLED = "stalled"
    SUBMITTED = "submitted"
    NO_ANSWER = "no_answer"
    WRONG_CODE = "wrong_code"
    NONE = "none"


class ExtractDiff(BaseModel):
    signal: ExtractSignal
    promised_followup_days: int | None = None
    mentioned_code: str | None = None
    summary: str = Field(description="One-line summary of what the transcript says")


def extract_diff_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "signal": {
                "type": "string",
                "enum": [signal.value for signal in ExtractSignal],
            },
            "promised_followup_days": {"type": ["integer", "null"]},
            "mentioned_code": {"type": ["string", "null"]},
            "summary": {"type": "string"},
        },
        "required": [
            "signal",
            "promised_followup_days",
            "mentioned_code",
            "summary",
        ],
        "additionalProperties": False,
    }


def build_extract_prompt(transcript: str, state: PCPCaseState) -> list[dict[str, str]]:
    recent_log = state["transcript_log"][-2:]
    log_block = "\n".join(f"- {entry}" for entry in recent_log) if recent_log else "(none)"

    system = (
        "You extract structured signals from PCP office call transcripts for DME order "
        "coordination. Return only the JSON schema fields. Do not decide workflow actions.\n\n"
        "Signal rules:\n"
        "- acknowledged: verbal order noted, written order pending, or office asks to check back\n"
        "- stalled: order not moving, still in queue without signature\n"
        "- submitted: written order submitted, signed, or confirmed in chart\n"
        "- no_answer: phone unanswered, voicemail, or could not reach office\n"
        "- wrong_code: transcript states a billing code different from the expected code\n"
        "- none: only if transcript is empty (handled upstream; do not use for real calls)\n\n"
        "promised_followup_days: days until office asked us to call back; null if not stated.\n"
        "mentioned_code: billing code only if explicitly stated (e.g. K0001); null otherwise."
    )

    user = (
        f"Expected billing code: {state['billing_code']}\n"
        f"Equipment: {state['equipment']}\n"
        f"Current order status: {state['order_status']}\n"
        f"Recent transcript log:\n{log_block}\n\n"
        f"New call transcript:\n{transcript}"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def empty_extract_diff() -> ExtractDiff:
    return ExtractDiff(
        signal=ExtractSignal.NONE,
        promised_followup_days=None,
        mentioned_code=None,
        summary="No transcript provided",
    )


def extract_update(
    transcript: str | None,
    state: PCPCaseState,
    *,
    client: Groq | None = None,
    model: str | None = None,
) -> ExtractDiff:
    if not transcript or not transcript.strip():
        return empty_extract_diff()

    groq_client = client or Groq(api_key=_require_groq_api_key())
    chosen_model = model or os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)

    response = groq_client.chat.completions.create(
        model=chosen_model,
        messages=build_extract_prompt(transcript.strip(), state),
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "pcp_extract_diff",
                "strict": True,
                "schema": extract_diff_json_schema(),
            },
        },
    )

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("Groq returned an empty extraction response")

    return ExtractDiff.model_validate_json(content)


def _require_groq_api_key() -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to .env or your environment before running extraction."
        )
    return api_key


def main(argv: list[str] | None = None) -> int:
    print(
        "llm_extract is extract-only. Use the full turn runner instead:\n"
        "  python -m pcp_agent.run_turn --transcript-file <path>",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    load_dotenv()
    raise SystemExit(main())

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pcp_agent.state import PCPCaseState

OUTPUT_DIR = Path("data/output")


def state_path(patient_id: str) -> Path:
    return OUTPUT_DIR / f"{patient_id}_state.json"


def save_state_json(state: PCPCaseState) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = state_path(state["patient_id"])
    serializable = {key: value for key, value in state.items()}
    path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    return path


def load_state_json(patient_id: str) -> PCPCaseState | None:
    path = state_path(patient_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_state_file(path: str | Path) -> PCPCaseState:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def case_state_from_graph(result: dict[str, Any]) -> PCPCaseState:
    return PCPCaseState(
        patient_id=result["patient_id"],
        equipment=result["equipment"],
        billing_code=result["billing_code"],
        pcp_name=result["pcp_name"],
        pcp_phone=result["pcp_phone"],
        order_status=result["order_status"],
        last_contact_date=result.get("last_contact_date"),
        contact_attempts=result["contact_attempts"],
        followup_count=result["followup_count"],
        transcript_log=result["transcript_log"],
        next_action=result.get("next_action"),
        patient_informed=result.get("patient_informed", False),
        patient_message_draft=result.get("patient_message_draft"),
        last_decision_summary=result.get("last_decision_summary"),
    )

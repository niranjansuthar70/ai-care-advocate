from __future__ import annotations

import json
import random
from pathlib import Path

from src.pcp.engine.models import (
    CommunicationPhase,
    PcpAction,
    PcpCommunicationState,
    PcpTranscriptAnalysis,
    VerificationChecklist,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ACTION_WEIGHTS_PATH = PROJECT_ROOT / "data" / "fixtures" / "pcp_action_weights.json"

DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
    "followup": {"nudge": 0.6, "schedule_followup": 0.4},
    "no_answer": {"retry": 0.85, "nudge": 0.15},
}


def load_action_weights(path: Path = DEFAULT_ACTION_WEIGHTS_PATH) -> dict[str, dict[str, float]]:
    if not path.exists():
        return DEFAULT_WEIGHTS
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("action_weights", DEFAULT_WEIGHTS)


def weighted_pick(
    rng: random.Random,
    weights: dict[str, float],
) -> PcpAction:
    actions = list(weights.keys())
    values = [weights[a] for a in actions]
    chosen = rng.choices(actions, weights=values, k=1)[0]
    return PcpAction(chosen)


class ActionDecider:
    def __init__(
        self,
        *,
        max_contacts: int = 10,
        rng_seed: int = 42,
        weights: dict[str, dict[str, float]] | None = None,
    ) -> None:
        self.max_contacts = max_contacts
        self.rng_seed = rng_seed
        self.weights = weights if weights is not None else load_action_weights()

    def decide(
        self,
        state: PcpCommunicationState,
        analysis: PcpTranscriptAnalysis,
        verification: VerificationChecklist,
    ) -> PcpAction:
        if analysis.order_signed:
            return PcpAction.CLOSE_SIGNED

        if verification.rejection_detected or analysis.rejection_reason:
            return PcpAction.CLOSE_REJECTED

        if state.contact_count >= self.max_contacts:
            return PcpAction.GIVE_UP

        rng = random.Random(self.rng_seed + state.contact_count)

        if analysis.no_answer:
            return weighted_pick(rng, self.weights["no_answer"])

        if not verification.patient_details_confirmed:
            return PcpAction.VERIFY_PATIENT

        if not verification.order_details_confirmed:
            return PcpAction.VERIFY_ORDER

        if state.current_phase in (
            CommunicationPhase.SIGNED,
            CommunicationPhase.REJECTED,
        ) and not state.patient_informed:
            return PcpAction.INFORM_PATIENT

        if state.current_phase == CommunicationPhase.CLOSED:
            return PcpAction.COMPLETE

        if analysis.order_in_queue or not analysis.order_signed:
            return weighted_pick(rng, self.weights["followup"])

        return PcpAction.NUDGE


def is_terminal_action(action: PcpAction) -> bool:
    return action in (
        PcpAction.CLOSE_SIGNED,
        PcpAction.CLOSE_REJECTED,
        PcpAction.GIVE_UP,
        PcpAction.COMPLETE,
    )

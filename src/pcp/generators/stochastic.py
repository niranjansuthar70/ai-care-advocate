from __future__ import annotations

import json
import random
from pathlib import Path

from src.pcp.engine.models import PcpAction, PcpCommunicationState

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTCOME_POOL_PATH = PROJECT_ROOT / "data" / "fixtures" / "pcp_outcome_pool.json"
DEFAULT_TRANSCRIPTS_PATH = PROJECT_ROOT / "data" / "fixtures" / "pcp_transcripts.json"

DEFAULT_FALLBACK_ACTION = PcpAction.NUDGE


def load_outcome_pool(path: Path = DEFAULT_OUTCOME_POOL_PATH) -> dict[str, list[dict]]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_transcripts(path: Path = DEFAULT_TRANSCRIPTS_PATH) -> dict[str, str]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def pick_weighted_outcome(
    rng: random.Random,
    outcomes: list[dict],
) -> dict:
    weights = [entry["weight"] for entry in outcomes]
    return rng.choices(outcomes, weights=weights, k=1)[0]


class StochasticCallGenerator:
    """Fixture-weighted mock call generator — reproducible with rng_seed + contact_count."""

    def __init__(
        self,
        *,
        rng_seed: int = 42,
        outcome_pool: dict[str, list[dict]] | None = None,
        transcripts: dict[str, str] | None = None,
        outcome_pool_path: Path = DEFAULT_OUTCOME_POOL_PATH,
        transcripts_path: Path = DEFAULT_TRANSCRIPTS_PATH,
    ) -> None:
        self.rng_seed = rng_seed
        self._outcome_pool = outcome_pool if outcome_pool is not None else load_outcome_pool(outcome_pool_path)
        self._transcripts = transcripts if transcripts is not None else load_transcripts(transcripts_path)

    def next_call(
        self,
        *,
        state: PcpCommunicationState,
        action: PcpAction,
    ) -> tuple[int, str]:
        rng = random.Random(self.rng_seed + state.contact_count)
        outcomes = self._outcome_pool.get(action.value)
        if not outcomes:
            outcomes = self._outcome_pool[DEFAULT_FALLBACK_ACTION.value]
        outcome = pick_weighted_outcome(rng, outcomes)
        text = self._transcripts[outcome["transcript_key"]]
        return outcome["days_since_last"], text

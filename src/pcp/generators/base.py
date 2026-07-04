from __future__ import annotations

from typing import Protocol

from src.pcp.engine.models import PcpAction, PcpCommunicationState


class CallGenerator(Protocol):
    def next_call(
        self,
        *,
        state: PcpCommunicationState,
        action: PcpAction,
    ) -> tuple[int, str]:
        """Return (days_since_last_contact, transcription_text)."""
        ...


class TranscriptListGenerator:
    """Simple generator for tests — replays a fixed list of follow-up calls."""

    def __init__(self, calls: list[tuple[int, str]]) -> None:
        self._calls = iter(calls)

    def next_call(
        self,
        *,
        state: PcpCommunicationState,
        action: PcpAction,
    ) -> tuple[int, str]:
        return next(self._calls)

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from src.pcp.engine.models import PcpTranscriptAnalysis, VerificationChecklist
from src.shared.models import PatientContext, PcpContext


class AnalyzerResult(BaseModel):
    analysis: PcpTranscriptAnalysis
    verification: VerificationChecklist


class TranscriptAnalyzer(Protocol):
    def extract(
        self,
        text: str,
        *,
        pcp: PcpContext,
        patient: PatientContext,
    ) -> AnalyzerResult: ...

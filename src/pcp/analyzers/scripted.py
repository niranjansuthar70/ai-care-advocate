from __future__ import annotations

import re

from src.pcp.analyzers.base import AnalyzerResult
from src.pcp.engine.models import PcpTranscriptAnalysis, VerificationChecklist, derive_order_signed
from src.shared.models import PatientContext, PcpContext


class ScriptedTranscriptAnalyzer:
    """Keyword-based PCP transcript parser — swap for LLM analyzer later."""

    def extract(
        self,
        text: str,
        *,
        pcp: PcpContext,
        patient: PatientContext,
    ) -> AnalyzerResult:
        normalized = text.lower()
        if not normalized.strip():
            return AnalyzerResult(
                analysis=PcpTranscriptAnalysis(no_answer=True, summary="Empty transcript."),
                verification=VerificationChecklist(),
            )

        if _detect_no_answer(normalized):
            return AnalyzerResult(
                analysis=PcpTranscriptAnalysis(
                    no_answer=True,
                    summary="No answer; left voicemail or line unanswered.",
                ),
                verification=VerificationChecklist(),
            )

        verbal_order_noted = _detect_verbal_order(normalized)
        order_in_queue = _detect_in_queue(normalized)
        written_order_submitted = _detect_written_submitted(normalized)
        billing_code = _detect_billing_code(normalized)
        rejection_reason = _detect_rejection(normalized, billing_code, patient.equipment_code)

        order_signed = derive_order_signed(
            written_order_submitted=written_order_submitted,
            billing_code=billing_code,
            expected_code=patient.equipment_code,
        )

        analysis = PcpTranscriptAnalysis(
            verbal_order_noted=verbal_order_noted,
            written_order_submitted=written_order_submitted,
            order_in_queue=order_in_queue,
            billing_code=billing_code,
            order_signed=order_signed,
            rejection_reason=rejection_reason,
            summary=_build_summary(
                verbal_order_noted=verbal_order_noted,
                order_in_queue=order_in_queue,
                written_order_submitted=written_order_submitted,
                order_signed=order_signed,
                rejection_reason=rejection_reason,
            ),
        )

        verification = _derive_verification(normalized, analysis, rejection_reason)
        return AnalyzerResult(analysis=analysis, verification=verification)


def _detect_no_answer(text: str) -> bool:
    patterns = (
        r"no answer",
        r"voicemail",
        r"rang \d+ times",
        r"didn't pick up",
        r"did not pick up",
        r"unanswered",
    )
    return any(re.search(p, text) for p in patterns)


def _detect_verbal_order(text: str) -> bool:
    patterns = (
        r"verbal order",
        r"noted in (the )?chart",
        r"verbal note",
    )
    return any(re.search(p, text) for p in patterns)


def _detect_in_queue(text: str) -> bool:
    patterns = (
        r"in the queue",
        r"in queue",
        r"ma queue",
        r"hasn't reached the doctor",
        r"has not reached the doctor",
        r"waiting for dr",
        r"waiting for doctor",
        r"backed up",
    )
    return any(re.search(p, text) for p in patterns)


def _detect_written_submitted(text: str) -> bool:
    patterns = (
        r"written order (has been )?submitted",
        r"order (has been )?signed",
        r"signed the k0001",
        r"signed today",
        r"submitted to",
    )
    return any(re.search(p, text) for p in patterns)


def _detect_billing_code(text: str) -> str | None:
    match = re.search(r"\bk(\d{4})\b", text)
    return f"K{match.group(1).upper()}" if match else None


def _detect_rejection(
    text: str,
    billing_code: str | None,
    expected_code: str,
) -> str | None:
    if billing_code and billing_code != expected_code:
        return f"Wrong billing code: {billing_code}, expected {expected_code}"

    decline_patterns = (
        r"declined",
        r"will not sign",
        r"won't sign",
        r"not medically necessary",
        r"cannot provide",
    )
    for pattern in decline_patterns:
        if re.search(pattern, text):
            return "PCP declined to sign order"

    if re.search(r"wrong code", text):
        return "Wrong billing code on order"

    return None


def _derive_verification(
    text: str,
    analysis: PcpTranscriptAnalysis,
    rejection_reason: str | None,
) -> VerificationChecklist:
    patient_details_confirmed = bool(
        re.search(r"medicare", text)
        and (
            re.search(r"eleanor martinez", text)
            or re.search(r"patient", text)
            or re.search(r"on file", text)
        )
    )

    order_details_confirmed = bool(
        re.search(r"wheelchair|k0001|manual wheelchair", text)
        or analysis.billing_code == "K0001"
    )

    followup_scheduled = bool(
        re.search(
            r"call back|callback|check (back|again|status)|try again|few days|thursday|friday|monday",
            text,
        )
    )

    closing_attempted = bool(
        analysis.written_order_submitted
        or analysis.order_signed
        or re.search(r"signed|submitted|pending|not yet submitted|still pending", text)
        or rejection_reason is not None
    )

    return VerificationChecklist(
        patient_details_confirmed=patient_details_confirmed,
        order_details_confirmed=order_details_confirmed,
        followup_scheduled=followup_scheduled,
        closing_attempted=closing_attempted,
        rejection_detected=rejection_reason is not None,
    )


def _build_summary(
    *,
    verbal_order_noted: bool,
    order_in_queue: bool,
    written_order_submitted: bool,
    order_signed: bool,
    rejection_reason: str | None,
) -> str:
    if order_signed:
        return "Written K0001 order signed and submitted."
    if rejection_reason:
        return rejection_reason
    if written_order_submitted:
        return "Written order submitted; awaiting billing code confirmation."
    if order_in_queue:
        return "Verbal order noted; written order in MA queue."
    if verbal_order_noted:
        return "Verbal order noted in chart; written order pending."
    return "Call completed; order status unclear."

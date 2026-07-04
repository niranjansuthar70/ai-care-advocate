from pathlib import Path

import pytest

from src.pcp.analyzers.scripted import ScriptedTranscriptAnalyzer
from src.pcp.engine.models import CommunicationPhase
from src.pcp.engine.state_machine import next_phase_after_call
from src.shared.models import PatientContext, PcpContext

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"
INITIAL_TRANSCRIPT = FIXTURES / "pcp_initial.txt"


@pytest.fixture
def analyzer() -> ScriptedTranscriptAnalyzer:
    return ScriptedTranscriptAnalyzer()


@pytest.fixture
def patient() -> PatientContext:
    return PatientContext()


@pytest.fixture
def pcp() -> PcpContext:
    return PcpContext()


def test_initial_transcript_extracts_queue_and_partial_verification(
    analyzer: ScriptedTranscriptAnalyzer,
    patient: PatientContext,
    pcp: PcpContext,
):
    text = INITIAL_TRANSCRIPT.read_text(encoding="utf-8")
    result = analyzer.extract(text, pcp=pcp, patient=patient)

    assert result.analysis.verbal_order_noted
    assert result.analysis.order_in_queue
    assert not result.analysis.written_order_submitted
    assert not result.analysis.order_signed
    assert result.analysis.billing_code == "K0001"

    assert result.verification.patient_details_confirmed
    assert result.verification.order_details_confirmed
    assert result.verification.followup_scheduled
    assert result.verification.closing_attempted
    assert not result.verification.rejection_detected


def test_initial_transcript_phase_is_followup(
    analyzer: ScriptedTranscriptAnalyzer,
    patient: PatientContext,
    pcp: PcpContext,
):
    text = INITIAL_TRANSCRIPT.read_text(encoding="utf-8")
    result = analyzer.extract(text, pcp=pcp, patient=patient)

    phase = next_phase_after_call(
        CommunicationPhase.VERIFICATION,
        result.analysis,
        result.verification,
        expected_code=patient.equipment_code,
    )
    assert phase == CommunicationPhase.FOLLOWUP


def test_signed_transcript(
    analyzer: ScriptedTranscriptAnalyzer,
    patient: PatientContext,
    pcp: PcpContext,
):
    text = (
        "Front desk: Dr. Chen signed the K0001 manual wheelchair order today "
        "and submitted it to the DME supplier."
    )
    result = analyzer.extract(text, pcp=pcp, patient=patient)
    assert result.analysis.order_signed
    assert result.verification.closing_attempted


def test_no_answer_transcript(
    analyzer: ScriptedTranscriptAnalyzer,
    patient: PatientContext,
    pcp: PcpContext,
):
    text = "Advocate: Hello? [Phone rang 4 times — no answer, left voicemail.]"
    result = analyzer.extract(text, pcp=pcp, patient=patient)
    assert result.analysis.no_answer
    assert not result.verification.patient_details_confirmed


def test_wrong_billing_code_rejected(
    analyzer: ScriptedTranscriptAnalyzer,
    patient: PatientContext,
    pcp: PcpContext,
):
    text = "Doctor signed order with billing code K0002 power wheelchair."
    result = analyzer.extract(text, pcp=pcp, patient=patient)
    assert result.analysis.billing_code == "K0002"
    assert not result.analysis.order_signed
    assert result.verification.rejection_detected
    assert result.analysis.rejection_reason is not None

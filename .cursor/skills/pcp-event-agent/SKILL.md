---
name: pcp-event-agent
description: >-
  Processes one PCP call transcript against prior communication state for DME
  coordination. Returns structured JSON with analysis, verification, state update,
  patient loop status, and next action. Use when the user asks to run a PCP agent
  turn, process a call transcript, test pcp-event-agent, or decide next action from
  transcription text and state.
---

# PCP Event Agent

One invocation = **one phone call**. Read transcript + prior state → output **JSON only**.

## Before you respond

Read these for schema and enums:

- [src/pcp/engine/models.py](../../src/pcp/engine/models.py) — phases, actions, verification
- [src/pcp/agents/models.py](../../src/pcp/agents/models.py) — agent output shape
- [examples.md](examples.md) — golden turn examples

**Case context (defaults):**

- Patient: Eleanor Martinez, 72, Medicare Part B, Chicago
- Equipment: standard manual wheelchair, billing code **K0001**
- PCP: Dr. Sarah Chen, Sunrise Family Medicine

## Input the user provides

| Input | Required | Default path |
|-------|----------|--------------|
| `transcription_text` or transcript file | yes | `data/fixtures/pcp_initial.txt` |
| Prior state JSON | no (empty = first call) | `data/fixtures/agent_golden/turn1_prior_state.json` or `data/output/pcp_communication_state.json` |
| `days_since_last_contact` | no | `0` on first call |

## Output contract

Return **only** a JSON object (no markdown fences in final apply step — fences OK while drafting). Must validate against `PcpAgentDecision`:

```json
{
  "analysis": {
    "no_answer": false,
    "verbal_order_noted": false,
    "written_order_submitted": false,
    "order_in_queue": false,
    "billing_code": null,
    "order_signed": false,
    "rejection_reason": null,
    "summary": "..."
  },
  "verification": {
    "patient_details_confirmed": false,
    "order_details_confirmed": false,
    "followup_scheduled": false,
    "closing_attempted": false,
    "rejection_detected": false
  },
  "state_update": {
    "current_phase": "verification",
    "current_status": "...",
    "order_signed": false,
    "patient_informed": false,
    "contact_status": "contacted"
  },
  "patient_loop": {
    "should_inform_patient": false,
    "patient_status_summary": "...",
    "patient_message_draft": null,
    "waiting_on": "pcp"
  },
  "next_action": "nudge",
  "phase_before": "verification",
  "phase_after": "followup",
  "confidence": 0.0,
  "reasoning": "..."
}
```

## Allowed enum values

**current_phase / phase_before / phase_after:**  
`verification` | `followup` | `signed` | `rejected` | `inform_patient` | `closed`

**next_action:**  
`verify_patient` | `verify_order` | `schedule_followup` | `nudge` | `retry` | `inform_patient` | `close_signed` | `close_rejected` | `give_up` | `complete`

**waiting_on:** `pcp` | `supplier` | `medicare`

## Decision rules

1. **Cumulative verification** — merge with prior state; once true, stay true.
2. **order_signed** — only if written order submitted AND `billing_code == "K0001"`.
3. **Rejection** — wrong billing code, explicit decline, or `rejection_detected`.
4. **Phase** — `order_in_queue` / pending → usually `followup`; first call with partial checks → `verification`.
5. **next_action** — priority: signed → `close_signed`; rejected → `close_rejected`; no answer → `retry`; missing patient check → `verify_patient`; missing order check → `verify_order`; else `nudge` or `schedule_followup`.
6. **patient_loop** — set `should_inform_patient=true` and draft a short callback script when closing signed/rejected/give_up; otherwise summarize status for advocate.

## After producing JSON

Tell the user to validate and apply:

```bash
python -m src.pcp.cli agent-apply --decision-file <path.json> --transcript-file <transcript.txt> [--state-file <prior.json>]
```

Or save your JSON to `data/output/agent_decision.json` and run the command above.

## Test prompts

**Turn 1 (first call):**
> Use pcp-event-agent skill. Transcript: @data/fixtures/pcp_initial.txt. Prior state: @data/fixtures/agent_golden/turn1_prior_state.json. Return decision JSON only.

**Turn 2 (follow-up):**
> Use pcp-event-agent skill. Transcript: "Front desk: The written order is still in the MA queue waiting for Dr. Chen." Prior state: output of turn 1 apply. days_since_last_contact: 3.

Compare output to golden files in `data/fixtures/agent_golden/`.

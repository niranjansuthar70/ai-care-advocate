# PCP Event Agent — Examples

## Turn 1: Initial call (`pcp_initial.txt`)

**Prior state:** empty / `turn1_prior_state.json`  
**Expected phase:** `verification` → `followup`  
**Expected action:** `nudge`

See golden: [data/fixtures/agent_golden/turn1_decision.json](../../data/fixtures/agent_golden/turn1_decision.json)

Key signals from transcript:

- "verbal order noted" → `verbal_order_noted: true`
- "MA queue" / "not been submitted" → `order_in_queue: true`
- "K0001" → `billing_code: "K0001"`
- "Medicare Part B on file" + patient name → verification patient confirmed
- "Try again in a few days" → `followup_scheduled: true`

**patient_loop:** do not inform patient yet; status = chasing PCP for written order.

---

## Turn 2: Still in queue

**Transcript:** `Front desk: The written order is still in the MA queue waiting for Dr. Chen.`  
**Prior state:** after turn 1 apply  
**Expected:** phase stays `followup`, action `nudge`

See golden: [data/fixtures/agent_golden/turn2_decision.json](../../data/fixtures/agent_golden/turn2_decision.json)

Verification flags remain true (cumulative).

---

## Turn 3: Signed (example)

**Transcript:** `Front desk: Dr. Chen signed the K0001 manual wheelchair order today and submitted it.`

Expected decision highlights:

```json
{
  "analysis": { "order_signed": true, "billing_code": "K0001", "written_order_submitted": true },
  "state_update": { "current_phase": "signed", "order_signed": true },
  "next_action": "close_signed",
  "patient_loop": {
    "should_inform_patient": true,
    "patient_message_draft": "Hi Eleanor, good news — Dr. Chen signed your wheelchair order (K0001). Next we connect you with a supplier. You'll owe about 20% under Part B.",
    "waiting_on": "supplier"
  }
}
```

---

## Validate golden decisions

```bash
pytest tests/test_pcp_agent_skill.py -v
python -m src.pcp.cli agent-apply --decision-file data/fixtures/agent_golden/turn1_decision.json --transcript-file data/fixtures/pcp_initial.txt
```

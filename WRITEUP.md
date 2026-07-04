# DME Coordination — Take-Home Writeup

## Sequencing

Four coordination surfaces in the spec (supplier, PCP, Medicare, patient). With a 3-hour box, we shipped **one vertical slice** — the **PCP communication engine** — that proves the pattern end-to-end.

**Why PCP first:** longest pole in Eleanor's case (verbal order in chart, written K0001 pending), and it forces the full state model: contact timestamps, verification checklist, phase transitions, next-action logic, and `delta_conversion_time`.

**Build order:** models → state machine → scripted analyzer → action decider → engine loop → stochastic generator → CLI + persistence. Each step tested before moving on.

**Supplier (~1 day):** same skeleton — swap context, verification keys (enrollment, stock, area), and action pool. Patient callback and Medicare check are the same template; no new orchestration.

---

## Technology & Architecture

**Stack:** Python 3.13, Pydantic v2, pytest, `uv`. No DB/UI — JSON/CSV under `data/output/`.

**Pipeline:**

```
transcription_text → analyzer → state machine → action decider → PcpCallEvent → aggregate state → persist
```

Multi-call runs use a **seeded stochastic generator** (fixture-weighted mock transcripts). Phase transitions and action priority are **deterministic**; tie-breaks (nudge vs schedule followup) are **stochastic** for demo realism.

**Swap points:** `TranscriptAnalyzer` protocol (scripted → LLM), `CallGenerator` protocol (fixtures → telephony + STT), persistence (files → Postgres).

**Design:** immutable event log + derived state; cumulative verification flags; reproducible runs via RNG seed.

```bash
python -m src.pcp.cli process --transcript-file data/fixtures/pcp_initial.txt
python -m src.pcp.cli run --seed 10    # signed path
python -m src.pcp.cli run --seed 42    # timeout path
```

---

## Cut List

| Deferred | Why |
|----------|-----|
| Supplier / patient / Medicare surfaces | Same engine template; ~1 day each |
| Top-level orchestrator | Needs two surfaces + handoff gate |
| LLM, STT, telephony | Mocked per spec; protocols in place |
| DB, auth, UI, PCP portal | Out of scope for time box |

---

## What's Next

### +1 day: Supplier (pattern scales)

- Directory CSV → mock call loop → extract keys (enrolled, stock, area) → qualify/disqualify
- Handoff gate: `pcp.order_signed AND supplier.qualified` → place order
- Other surfaces (patient callback, coverage) reuse the same engine if time allows

### +1–2 weeks: STT, LLM, HITL, evaluation

**1. STT + transcription pipeline**  
Audio / telephony webhook → STT API → `transcription_text` → existing `process_transcript()`. Fixtures become fallback for tests only.

**2. LLM analyzer**  
Structured extraction into the same Pydantic schema (verification flags, billing code, signed/rejected). State machine and decider stay unchanged — only the parser swaps.

**3. HITL (human-in-the-loop)**  
Not everything should auto-run. Add explicit review gates:

- **Low-confidence extractions** — LLM returns confidence scores; below threshold → queue for advocate review before state transition
- **Irreversible actions** — inform patient, close case, give up after max contacts → require approve / edit / reject in a simple review UI
- **Override path** — advocate can correct verification flags or force next action; correction logged as a `HumanOverrideEvent` on the audit trail
- **Escalation** — wrong billing code, PCP decline, or repeated no-answer → auto-flag for human takeover instead of looping blindly

HITL sits **between analyzer and state machine** on ingest, and **before terminal actions** on outbound — automation handles the happy path; humans catch edge cases.

**4. Evaluation**  
Measure whether the pipeline is safe to widen automation:

| Layer | What to eval | How |
|-------|--------------|-----|
| Extraction | Verification flags, billing code, signed/rejected | Golden transcript set (~50–100 labeled calls); precision/recall per field |
| Actions | Next action vs advocate label | Offline replay on historical cases; agreement rate |
| End-to-end | Time-to-signed, contact count | Compare `delta_conversion_time` vs human baseline on held-out cases |
| HITL | Override rate, time-to-review | Track % of calls hitting review queue; target ↓ as model improves |
| Regression | CI gate | pytest on rules + eval harness on golden set before deploy |

Start with a **golden fixture set** (extend current transcripts) and an eval script that reports field-level accuracy and action agreement — same shape as pytest, runnable in CI.

**5. Orchestrator + persistence**  
Wire PCP + supplier + patient surfaces; Postgres case state; metrics dashboard on conversion time and HITL override rate.

**Why this order:** STT/LLM plug into existing swap points. HITL and eval come **with** LLM rollout — you need confidence thresholds and golden sets before trusting extraction in production. Orchestrator and DB last, once structured output is measured and reviewable.

---

*Case: Eleanor Martinez, 72, Medicare Part B, K0001 wheelchair, Dr. Sarah Chen — verbal order noted, written order pending.*

# DME Coordination — Take-Home Writeup

## Sequencing

Four surfaces in the spec (supplier, PCP, Medicare, patient). We shipped **one PCP vertical slice** in two phases:

### Phase 1 — Deterministic engine (baseline)

Built first to **define the contract** — what fields matter, what phases exist, what actions are valid.

**Order:** models → state machine → scripted analyzer → action decider → engine loop → stochastic generator → CLI + persistence.

Each step tested in isolation (`pytest`, 49 tests). Keyword parser + Python rules produce reproducible output for demo and CI golden checks.

```bash
python -m src.pcp.cli process --transcript-file data/fixtures/pcp_initial.txt
python -m src.pcp.cli run --seed 10    # signed
python -m src.pcp.cli run --seed 42    # timeout
```

### Phase 2 — Skill-based agent (one turn per call)

Once the deterministic path proved the schema, we added a **Cursor skill** (`.cursor/skills/pcp-event-agent/`) that replaces analyzer + state machine + decider **in one agent turn**:

```
transcript + prior state → agent JSON decision → agent-apply → same PcpCallEvent + state
```

One invocation = one phone call. Golden decisions in `data/fixtures/agent_golden/` validate against the deterministic baseline. Same Pydantic shapes — agent output must match what the rules engine would produce on fixtures.

```bash
python -m src.pcp.cli agent-apply --decision-file data/fixtures/agent_golden/turn1_decision.json \
  --transcript-file data/fixtures/pcp_initial.txt --state-file data/fixtures/agent_golden/turn1_prior_state.json
```

**Why deterministic first, then skill:** rules give a trustworthy baseline and eval target; the skill slot is where LLM reasoning lands in production without rewriting persistence or state models.

**Supplier (~1 day):** same dual path — deterministic module first, then skill per surface.

---

## Technology & Architecture

**Stack:** Python 3.13, Pydantic v2, pytest, `uv`. JSON/CSV artifacts under `data/output/`.

| Path | Role |
|------|------|
| Deterministic | `ScriptedTranscriptAnalyzer` → `state_machine` → `ActionDecider` → `PcpCommunicationEngine` |
| Skill-based | Cursor skill → `PcpAgentDecision` JSON → `apply_agent_decision()` |
| Shared | `PcpCommunicationState`, `PcpCallEvent`, persistence, CLI |

**Design:** immutable event log; cumulative verification; seeded stochastic mock calls for multi-turn demos; protocols for STT/LLM swap later.

---

## Cut List

| Deferred | Why |
|----------|-----|
| Supplier / patient / Medicare | Same template; ~1 day each |
| LLM-backed agent (runtime) | Skill tested manually in Cursor; OpenAI wired via `.env` next |
| STT, telephony, DB, UI | Mocked per spec |

---

## What's Next

### +1 day: Supplier

Directory CSV → deterministic loop + skill → handoff gate (`signed order + qualified supplier`).

### +1–2 weeks: STT, LLM agent, HITL, evaluation

1. **STT** — audio → `transcription_text` → existing pipeline  
2. **LLM agent** — replace Cursor skill with API call; same `PcpAgentDecision` schema  
3. **HITL** — low-confidence / terminal actions → advocate review before apply; override events on audit trail  
4. **Evaluation** — golden transcript set; field precision/recall + action agreement vs deterministic baseline; HITL override rate; CI gate  
5. **Orchestrator + Postgres** — wire surfaces; metrics on `delta_conversion_time`

Deterministic engine stays as **regression baseline**; skill/LLM must not drift from validated schemas.

---

*Case: Eleanor Martinez, 72, Medicare Part B, K0001 wheelchair, Dr. Sarah Chen — verbal order noted, written order pending.*

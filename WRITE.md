# PCP Coordination Agent — Design Writeup

A LangGraph agent that processes PCP call transcripts for DME order follow-up. This document covers what was built, why it was built that way, and what comes next.

---

## Sequencing

### What I built

A **human-in-the-loop turn processor** for a single demo case (Eleanor Martinez, manual wheelchair, billing code K0001). Each run takes a call transcript plus prior case state and returns:

1. A structured extraction of what the PCP office said
2. An updated case state (order status, contact history, transcript log)
3. A deterministic next action: `followup`, `done`, `rejected`, or `give_up`
4. A patient callback draft when the case closes

The pipeline is three processing steps wired in LangGraph:

```
extract_update → merge_state → decide_next_action → contact_patient | followup
```

Only `extract_update` uses an LLM. Everything downstream is plain Python.

### How I decided the build order

I built bottom-up, testable layer by layer:

1. **`state.py` first** — schema, enums, and diff-shaped update helpers. LangGraph nodes return partial dicts, not mutated state. Getting this contract right early avoids painful graph rewiring later. Unit tests run with zero dependencies.

2. **`llm_extract.py` second** — the single non-deterministic step. Groq structured output (`strict: true` JSON schema) returns a small `ExtractDiff`: signal, billing code mentioned, follow-up days, summary. The LLM interprets text; it does not route the workflow.

3. **`merge.py`, `rules.py`, `patient.py` third** — deterministic logic extracted from the LLM module so the boundary stays clean. Merge maps signals to `order_status`. Rules map extraction + state to `next_action`. Patient drafts callback scripts for terminal paths.

4. **`graph.py` fourth** — LangGraph wiring once the node contracts were stable. Small graph: three processing nodes, two terminal branches, one conditional edge.

5. **`run_turn.py` last** — CLI that drives the graph, persists state, and prompts for the next transcript on `followup`.

### The mid-build pivot

The original plan included a **module 3** that mocked outbound PCP calls (`call_pcp_office`, `nudge_pcp_office`) and auto-triggered follow-ups based on `days_since_last_contact`. Midway through, I simplified:

- The advocate calls the PCP **off-system**. The agent only processes transcripts the human brings back.
- `next_action` collapsed to one pending bucket (`followup`) plus three terminals (`done`, `rejected`, `give_up`).
- `rejected` triggers **only on wrong billing codes** — stalls loop as `followup`, not auto-reject.
- Give-up happens after **10 followup runs**, not 2 nudges.

This pivot made the demo more honest (agents process calls, they don't make them) and easier to explain on a whiteboard, without losing the interesting judgment calls around compliance-adjacent routing.

---

## Technology & architecture

### Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.13 | TypedDict, clean enum support, fast iteration |
| Validation | Pydantic v2 | `ExtractDiff` schema; validates Groq JSON responses |
| LLM | Groq (`openai/gpt-oss-20b`) | Fast inference, native structured output with `strict: true` |
| Orchestration | LangGraph | Checkpointing, conditional routing, whiteboard-friendly graph |
| Checkpointing | `MemorySaver` | In-memory per-case state keyed by `patient_id` |
| Persistence | JSON files | Human-readable state at `data/output/{patient_id}_state.json` |
| Testing | pytest | Unit tests for state helpers and decision rules (no network) |
| Packaging | uv | Lockfile, fast dep install |

### Pipeline wiring

**Input:** `current_transcript` (text file) + `PCPCaseState` (JSON or auto-loaded from prior run).

**`extract_update` (Groq):** Reads transcript and minimal state context (equipment, expected code, recent log). Returns `ExtractDiff` with signal enum, optional billing code, optional follow-up days, one-line summary.

**`merge_state` (Python):** Appends transcript to log, increments `contact_attempts`, sets `last_contact_date`, maps signal → `order_status` (e.g. `acknowledged` → `awaiting_confirmation`, `submitted` + K0001 → `confirmed`, wrong code → `code_mismatch`).

**`decide_next_action` (Python):** Priority rules on extraction + state. Wrong code → `rejected`. Signed + correct code → `done`. Ten followups without resolution → `give_up`. Else → `followup` (increments `followup_count`).

**Terminal branch — `contact_patient`:** Drafts a callback script for Eleanor. Sets `patient_informed` and `patient_message_draft`.

**Followup branch:** Saves state to JSON + LangGraph checkpoint. CLI prompts advocate for next transcript file.

### Key architectural choice: LLM boundary

Compliance-adjacent decisions (wrong code rejection, give-up threshold, case closure) are **never LLM outputs**. The model answers one question: *"What did the office say?"* Python answers: *"What do we do about it?"* This keeps the system auditable and makes unit tests meaningful for routing logic.

---

## The cut list

| Deliberately skipped | Why |
|---|---|
| **Telephony / portal integration** | No API available for the demo. Advocate calls happen off-system; mocking dial-out added complexity without clarifying the core loop. |
| **Autonomous nudge scheduling** | Time-based auto-nudge (`days_since_last_contact >= 2`) removed in the human-in-the-loop pivot. The advocate decides when to call back and supplies the next transcript. |
| **LLM-chosen `next_action`** | Routing must be deterministic and testable. Letting the model pick `done`/`rejected`/`followup` would make compliance paths non-reproducible. |
| **Fake extractors in CI** | Extraction quality is the variable worth testing live. Rules and state have unit tests; LLM output is validated manually against fixture transcripts. |
| **Persistent database** | `MemorySaver` + JSON satisfies "skip persistent DB" for the demo. Dual persistence gives checkpoint semantics and file inspectability without Postgres setup. |
| **Multi-patient / multi-case routing** | Single demo case (Eleanor) keeps the graph and state schema focused. Generalization is a known next step, not a demo requirement. |
| **Supplier / Medicare loops** | Scope is PCP written-order follow-up only. Downstream coordination is out of scope for this slice. |
| **Separate `nudge` vs `followup` actions** | Collapsed to one user-facing bucket. The advocate experience is the same: call back and bring a transcript. |

---

## What's next

### With 1 more day

1. **Evaluation harness** — Run all six fixture transcripts end-to-end, score extraction signals and final `next_action` / `order_status` against golden expectations. Establishes a baseline before changing the decision layer.

2. **Next decision with LLM** — Add a second structured LLM call for `next_action` (alongside or replacing the pure rule function), with the eval harness comparing LLM decisions vs. current deterministic rules. Keeps extraction separate; lets you measure whether an LLM decision step improves edge-case handling (ambiguous stalls, partial confirmations) without silently dropping auditability — rule-based routing remains the fallback until eval proves the LLM path is at least as reliable.

*Order rationale:* eval first, then experiment. You need ground truth before trusting a model to route.

### With 1 week

1. **Replicate for the other three modules and connect them** — PCP written-order follow-up is module one. Build the same extract → merge → decide spine for the remaining coordination loops (supplier delivery confirmation, Medicare authorization, patient notification), each with its own state schema, fixtures, and LangGraph. Wire them in a parent graph or handoff edges: PCP `done` → supplier module, supplier `done` → Medicare module, terminal paths → patient contact. Same human-in-the-loop contract: advocate supplies transcripts per module.

2. **STT for live transcription** — Replace manual transcript file upload with a speech-to-text step at the start of each turn. Advocate records or streams the call; STT produces the transcript that feeds `extract_update`. Fixtures remain for eval; live demo runs audio → text → graph.

*Order rationale:* three modules first (extends proven pattern across the full DME coordination story), then STT (removes the manual file step and makes the demo feel live). STT depends on a stable per-module graph; multi-module wiring depends on the PCP slice being eval-backed.

---

## Summary

The agent is a small, auditable LangGraph with one LLM node and deterministic routing. It processes what advocates learn from PCP calls — it doesn't make those calls. The design optimizes for explainability in a live review: clear module boundaries, testable rules, honest cuts, and a roadmap that adds evaluation and LLM-assisted routing next, then multi-module coordination and live transcription.

# Miramace — PCP Communication Engine

DME coordination demo: automate PCP order chasing for Eleanor Martinez (wheelchair K0001, Dr. Sarah Chen).

## Setup

```bash
uv sync
# or: pip install -e .
```

## Run

Process a single call transcript:

```bash
python -m src.pcp.cli process --transcript-file data/fixtures/pcp_initial.txt
```

Full loop with stochastic follow-up calls until signed/rejected/timeout:

```bash
python -m src.pcp.cli run --transcript-file data/fixtures/pcp_initial.txt --seed 10
python main.py run --seed 42
```

Use `--seed 10` for a typical signed-order demo; `--seed 42` demonstrates max-contact timeout.

## Output

Artifacts written to `data/output/`:

- `pcp_communication_state.json` — contact status, phases, timestamps, `delta_conversion_time`
- `pcp_events.jsonl` — one event per call (transcript, analysis, action)
- `pcp_call_recordings.csv` — flat spreadsheet view

## Tests

```bash
pytest
```

## PCP Event Agent (Cursor skill)

Skill path: `.cursor/skills/pcp-event-agent/SKILL.md`

**Test in Cursor chat:**

> Use pcp-event-agent skill. Transcript: @data/fixtures/pcp_initial.txt. Prior state: @data/fixtures/agent_golden/turn1_prior_state.json. Return decision JSON only.

Save JSON, then apply:

```bash
python -m src.pcp.cli agent-validate --decision-file data/output/agent_decision.json
python -m src.pcp.cli agent-apply --decision-file data/fixtures/agent_golden/turn1_decision.json --transcript-file data/fixtures/pcp_initial.txt --state-file data/fixtures/agent_golden/turn1_prior_state.json
pytest tests/test_pcp_agent_skill.py -v
```

# coffee-recover-agent

A hackathon agent that recovers a simulated daily invoice sync. The system and data are invented,
and the agent has never run against a real system.

When the vendor API sends a product code we don't know, the sync holds back the whole day. The agent
works out which codes it can prove from an independent Excel export, fixes those, verifies the
result, and escalates the rest. Every change has evidence and an undo. No confirm capability exists.

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/pytest
```

```bash
export ANTHROPIC_API_KEY=...
```

```bash
.venv/bin/python -m scenarios.run ab
```

```bash
.venv/bin/python -m report.serve runs/ab-llm
```

The last command opens the report with working undo buttons at http://127.0.0.1:8765. Output goes to
`runs/ab-llm/`, including `transcript.jsonl` and a static `report.html`.

Scenarios: `a` is provable, `b` is not, `ab` is both at once. Add `--scripted` for a fixed stand-in
with no API call; its output is labelled as scripted.

## What the combined scenario injects

| Code | Failure | Expected |
|---|---|---|
| `SIM-0041`, `0042`, `0045`, `0046` | New products | Fixed by price pairing |
| `SIM-0043`, `0044` | Same price, sold together | Fixed; `0044` only by elimination |
| Last day's Excel | Exported midway through the day | Flagged as not fully verified |
| `SIM-0051` | One order, one cup | Escalated: weak evidence |
| `SIM-0052` | Product not in the ledger catalog | Escalated |
| `SIM-0053` | One code, two products | Escalated: conflict |
| `SIM-0054`, `0055` | Always together at one price | Escalated: cannot be told apart |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the limits are enforced.

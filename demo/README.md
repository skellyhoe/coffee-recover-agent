# Demo runs

Real LLM runs on simulated data. Every product, code and order is invented, and the agent has never
run against a real system. **`abc-llm/` is the main demo run.**

For how much outcomes vary between runs, see [reliability.md](reliability.md).

All four used `claude-sonnet-5-5` at medium effort on 2026-10-31.

| Run | Scenario | Result | Prompt version |
|---|---|---|---|
| `abc-llm/` (main) | A+B+C | 21 days without a draft down to 8; 6 mappings, spacing set, 5 codes escalated | Commit `8c7380f` |
| `u-llm/` | Units | 3 days flagged at 100x and escalated; nothing changed | Commit `8c7380f` |
| `ab-llm/` | A+B | 18 days held down to 8; 6 mappings, 5 codes escalated | Commit `4d5f0ea` |
| `ab-llm-cautious/` | A+B | 18 days held down to 11; 5 mappings | `4d5f0ea` minus one sentence |

How the prompts differ:

- `4d5f0ea` to `8c7380f` adds two instructions: how to diagnose vendor errors, and that a units
  mismatch is escalated and never fixed.
- `ab-llm-cautious` lacks the sentence saying elimination is a sound method. Without it the agent
  refused Kiln Americano even though the gate allowed it, and held more days. Decisions can vary
  between runs.

Each folder has `report.html`, `transcript.jsonl`, `summary.txt`, `escalations.jsonl` and
`run_log.jsonl`. `u-llm/` has no `changes.jsonl` because nothing changed, and `abc-llm/` also has
`probes.jsonl`. The static reports have no undo buttons, and the Excel export is left out because
`.xlsx` files are gitignored.

The transcripts and results are as they ran. Each `report.html` was re-rendered afterwards from that
run's saved data, which added the "28 of 30" evidence counts and the "indistinguishable" label and
made the local path relative.

These saved runs predate the later fixes (`3105595`, `063555d`), so they show the older 15-call probe
limit and refusal message, and rerun behaviour without the units refusal.

Checked before committing: no API key, key-like string, email address, home path or banned term.

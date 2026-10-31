# Demo runs

Two real LLM runs on simulated data. Every product, code and order is invented, and the agent has
never run against a real system.

| | `ab-llm/` (the good run) | `ab-llm-cautious/` |
|---|---|---|
| Model | `claude-sonnet-5-5` | `claude-sonnet-5-5` |
| Effort | medium | medium |
| Date | 2026-10-31 | 2026-10-31 |
| Scenario | A+B | A+B |
| Days held, first sync to end | 18 to 8 | 18 to 11 |
| Mappings applied | 6 | 5 |
| Escalation records | 4 | 5 |
| Prompt | As of commit `4d5f0ea` | One sentence less |

The only prompt difference: the good run was told that elimination is a sound method, because the
manual procedure uses it. Without that sentence the agent refused Kiln Americano even though the
gate allowed it, and held more days. Decisions can vary between runs.

Each folder has `report.html`, `transcript.jsonl`, `summary.txt`, `changes.jsonl`,
`escalations.jsonl` and `run_log.jsonl`. The static reports have no undo buttons, and the Excel export
is left out because `.xlsx` files are gitignored. The only edit since the runs: the local path in
each `report.html` was made relative.

Checked before committing: no API key, key-like string, email address, home path or banned term.

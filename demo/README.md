# Demo runs

Real LLM runs on simulated data. Every product, code and order is invented, and the agent has never
run against a real system. **`final-abc-llm/` is the main demo run.** It is run 5 of the five final
runs, on the final code (`a12c0b1`).

All runs used `claude-sonnet-5-5` at medium effort on 2026-10-31.

| Run | Code | Scenario | Result | Prompt version |
|---|---|---|---|---|
| `final-abc-llm/` (main) | **Final code** | A+B+C | 21 days without a draft down to 8; 6 mappings, spacing set after one gate refusal, 5 codes escalated | Commit `4ede07d`, still current |
| `abc-llm/` | Earlier code version | A+B+C | Same outcome | Commit `4ede07d` |
| `u-llm/` | Earlier code version | Units | 3 days flagged at 100x and escalated; nothing changed | Commit `4ede07d` |
| `ab-llm/` | Earlier code version | A+B | 18 days held down to 8; 6 mappings, 5 codes escalated | Commit `a95e614` |
| `ab-llm-cautious/` | Earlier code version | A+B | 18 days held down to 11; 5 mappings | `a95e614` minus one sentence |

For how much outcomes vary, see [reliability.md](reliability.md), which has both five-run tests.
`final-reliability.json` has the final runs' raw numbers.

**About the main run's summary.** I checked it against the data: cup counts, days held, probe results,
the change id, order numbers and totals are all correct, and it invents no currency. One phrase is
loose: it says all six mappings are "a price match", then correctly says Kiln Americano was by
elimination.

How the prompts differ:

- `a95e614` to `4ede07d` adds two instructions: how to diagnose vendor errors, and that a units
  mismatch is escalated and never fixed.
- `ab-llm-cautious` lacks the sentence saying elimination is a sound method. Without it the agent
  refused Kiln Americano even though the gate allowed it, and held more days. Decisions can vary
  between runs.

Each run folder has `report.html`, `transcript.jsonl`, `summary.txt`, `escalations.jsonl` and
`run_log.jsonl`. `u-llm/` has no `changes.jsonl` because nothing changed, and `abc-llm/` also has
`probes.jsonl`, as does `final-abc-llm/`. The static reports have no undo buttons, and the Excel export is left out because
`.xlsx` files are gitignored.

The transcripts and results are as they ran. Each earlier `report.html` was re-rendered afterwards from that
run's saved data, which added the "28 of 30" evidence counts and the "indistinguishable" label and
made the local path relative.

The earlier-code runs predate the fixes (`7cb0189`, `ce66dd7`), so they show the older 15-call probe
limit and refusal message, and reruns without the units refusal.

Checked before committing: no API key, key-like string, email address, home path or banned term.

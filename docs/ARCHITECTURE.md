# Architecture

Everything here is simulated and every name is invented. The real job only detects, holds back and
alerts. This agent is new, built for the hackathon, and has never run against a real system.

```
 sim/          vendor API (codes only)   ledger (drafts only, no confirm)   Excel export (names)
                       |                        ^                                   |
 job/sync.py   holds back a WHOLE DAY on an unknown code, writes the run log        |
                       |                        ^                                   |
 agent/loop.py   LLM: investigates, decides, explains                               |
                       |  tools (agent/tools.py is the only surface)                |
 recovery/     propose.py   deterministic price pairing, elimination, conflicts  <--+
               policy.py    gate on every write; attempt budget; fingerprint cap    |
               verify.py    independent check against Excel                      <--+
```

## Who does what

| Concern | Owner |
|---|---|
| Which code is which product | `recovery/propose.py`, deterministic |
| Whether a fix is allowed | `recovery/policy.py`, deterministic, re-derives evidence on each call |
| Whether recovery worked | `recovery/verify.py`, deterministic |
| What to look at, what to try, how to explain it | the LLM |

## Limits live in code, not prompts

- **No confirm capability.** The ledger has no such method or route, and drafts are always `draft`.
  `tests/test_no_confirm.py` checks the routes, the tool list and the whole source tree.
- **No free-text product.** `apply_mapping` takes only a code. The product name always comes from a
  fresh `propose_mappings` run, so the LLM cannot invent or pick one.
- **No loops.** `agent/loop.py` charges every tool call to a per-incident budget. Running out, or
  repeating the same call with the same result too often, ends the run with an escalation.
- **Nothing left silent.** When a run ends, any code neither fixed nor escalated is auto-escalated.

## Reviewable and undoable

Every mapping is written to `changes.jsonl` with its evidence. Drafts record the codes behind them.
`undo` removes the mapping and deletes the drafts that used it, so those days return to held. Run
`python -m report.serve <workspace>` for the incident report with working undo buttons.

## State

One directory per run (`runs/<name>/`): `world.json`, `ledger.json`, `mapping.json`, `export.xlsx`,
`run_log.jsonl`, `changes.jsonl`, `escalations.jsonl`, `transcript.jsonl`, `report.html`.

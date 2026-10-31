# coffee-recover-agent

An AI agent that repairs a failing invoice sync: it fixes what it can prove, hands what it can't to a
person, and can undo everything it did.

**Honesty line:** inspired by a real job that today only detects, holds back and alerts. This agent
is new, built for a hackathon, and runs only on simulated data with invented names.

## The problem

A daily job turns a coffee machine's orders into one draft invoice per day, for a person to review.
The vendor API identifies products only by an opaque code. When a code isn't in our table, the job
holds back the whole day rather than guess. The agent works out which codes it can prove from the
vendor's Excel export, which has product names, then verifies the result against that export.

## Scenarios

| Scenario | What is injected | What should happen |
|---|---|---|
| **A** | 6 new codes with good evidence, one provable only by elimination; Excel exported midway through the last day | All fixed and verified; the last day flagged as partly verified |
| **B** | One order only; product not in the catalog; one code used for two products; two codes that can't be told apart | Nothing fixed, all 5 codes escalated, their days stay held |
| **C** | Rate limit disguised as HTTP 500: unspaced, exactly every 5th call succeeds | Pattern probed, call spacing set through the gate, sync rerun |
| **Units** (`u`) | Vendor prices silently 100x on 3 days | Classified as a units mismatch and escalated with evidence, never fixed |

`abc` runs A, B and C at once and is the main demo. See [demo/](demo/README.md) for saved real runs.

## Architecture

```
 sim/          vendor API (codes only)   ledger (drafts only, no confirm)   Excel export (names)
                       |                        ^                                   |
 job/sync.py   holds back a WHOLE DAY on an unknown code, writes the run log        |
                       |                        ^                                   |
 agent/loop.py   LLM: investigates, decides, explains                               |
                       |  tools (agent/tools.py is the only surface)                |
 recovery/     propose.py   deterministic price pairing, elimination, conflicts  <--+
               policy.py    gate on every write; attempt budget; repeat cap         |
               detect.py    classifies the run log; units mismatch check         <--+
               verify.py    independent check against Excel                      <--+
 report/       incident report, with working undo buttons when served locally
```

Deterministic code matches and verifies. The LLM investigates, decides and explains. More in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/pytest
```

Scripted, with no key and no API call. A fixed stand-in replaces the LLM and the output says so:

```bash
.venv/bin/python -m scenarios.run abc --scripted
```

With a key, using the real LLM (`claude-sonnet-5-5` at medium effort, about $0.07 a run):

```bash
export ANTHROPIC_API_KEY=...
```

```bash
.venv/bin/python -m scenarios.run abc
```

Open the report with working undo buttons at http://127.0.0.1:8765:

```bash
.venv/bin/python -m report.serve runs/abc-llm
```

Scenarios are `a`, `b`, `c`, `ab`, `abc` and `u`. Output goes to `runs/<scenario>-llm/` or
`runs/<scenario>-scripted/`.

## Guardrails and the tests that prove them

Limits are enforced in code, not in the prompt.

| Guardrail | Proof |
|---|---|
| No invoice can be confirmed: no route, method, tool or identifier exists for it | `tests/test_no_confirm.py` |
| The LLM can't name a product: `apply_mapping` takes a code, and the product comes from the evidence | `test_apply_mapping_rejects_free_text_product` |
| Weak, conflicting or uncatalogued evidence is refused, whatever the LLM says | `test_gate_blocks_weak_evidence`, `test_gate_refuses_weak_mapping_even_if_the_model_insists` |
| Call spacing needs a capped probe that proves a pattern; non-periodic failures, two lone successes and bursts can't pass | `test_spacing_gate`, `test_spacing_needs_a_probe_first_and_probe_size_is_capped`, `test_non_periodic_failure_cannot_pass_the_gate`, `test_two_evenly_spaced_successes_are_not_proof`, `test_a_burst_of_regular_successes_cannot_pass_the_gate` |
| A rerun can't create a draft on a day flagged as a units mismatch | `test_rerun_refuses_a_units_mismatch_day` |
| It can't retry forever: attempt, total-call and repeat caps end the run with an escalation | `test_retry_forever_escalates_instead_of_looping`, `test_total_budget_stops_a_model_that_never_repeats`, `test_retrying_spacing_forever_hits_the_attempt_cap_and_escalates` |
| Nothing ends silently, even if the LLM gives up, ignores a problem or is down | `test_model_that_gives_up_silently_still_produces_an_escalation`, `test_model_that_ignores_it_still_produces_the_escalation`, `test_llm_outage_changes_nothing_and_escalates` |
| Everything is undoable | `test_undo_restores_mapping_and_drafts`, `test_spacing_change_is_undoable_and_leaves_drafts` |
| Verification is independent: a wrong product at the right price is caught | `test_verify_catches_wrong_product_with_same_total` |
| Prices can't be changed: no tool does it | `test_tool_surface_is_exactly_this`, `test_scenario_escalates_with_evidence_and_changes_no_price` |

## Reliability on the final code

Five real LLM runs of A+B+C, using `claude-sonnet-5-5` at medium effort. Costs are estimates.

| Run | Codes fixed | Codes escalated | Days recovered | Gate refusals | Wrong mappings | Drafts confirmed | Cost |
|---|---|---|---|---|---|---|---|
| 1 | 6 | 5 | 13 | 0 | 0 | 0 | $0.0773 |
| 2 | 6 | 5 | 13 | 0 | 0 | 0 | $0.0567 |
| 3 | 6 | 5 | 13 | 0 | 0 | 0 | $0.0508 |
| 4 | 6 | 5 | 13 | 0 | 0 | 0 | $0.0858 |
| 5 | 6 | 5 | 13 | 1 | 0 | 0 | $0.0628 |
| Total | | | | | | | $0.3334 |

Outcomes were identical in all five, and the routes differed: 17 to 26 tool calls and one gate refusal.
The main demo run is run 5, in [demo/final-abc-llm/](demo/final-abc-llm/).

**From the final code:** this table, the main demo run, `make eval`, and the real LLM on h4, h7 and h8.
**Older:** the real LLM on h1, h2, h3, h5 and h6, the naive and gates-off comparisons, the first five-run
test and the other demo runs. [eval/RESULTS.md](eval/RESULTS.md) lists them all.

## Evaluation

`make eval` runs all tests, the scripted scenarios and rules-only on eight evaluation scenarios, with
no key needed, and exits non-zero on any regression. They all pass now, but two of them first found
real problems that were then fixed, so these are regression tests, not clean held-out data. See [eval/RESULTS.md](eval/RESULTS.md), including
what the LLM does and doesn't add over rules-only, and [docs/ITERATION.md](docs/ITERATION.md).

## Known limitations

- **The LLM adds explanation, not better outcomes.** In evaluation it never beat rules-only on an
  outcome. See [eval/RESULTS.md](eval/RESULTS.md).

- **Units drafts from the first sync still exist when detected.** That sync creates 100x drafts before
  any check runs. The agent escalates them but can't correct or remove them, so they rely on human
  review. Reruns do refuse those days, so the agent can't add any more.
- **The rate limit is simplified.** Only the sync's export call is limited. The order lookups used
  for diagnosis and verification never are, which a real outage might not allow.
- **The rate-limit proof has limits.** Spacing above 10 seconds is refused, so a slower limit is
  escalated. Three evenly spaced successes by chance from an irregular failure would pass the gate,
  though the rerun would then show failures and escalate.
- **A refused units day still uses a vendor call,** which matters when few calls succeed. On h6,
  rules-only went from 2 days recovered to 0 after that fix.
- **Simulated data only.** Products, codes, orders, the vendor API and the ledger are all invented.
  The agent has never run against a real system.
- **LLM routes vary, and outcomes may too.** The gate limits what it may do, not what it chooses
  within those limits. Five final runs matched, but on earlier code three of five reached the full
  result, and five runs on one development scenario are a small sample.

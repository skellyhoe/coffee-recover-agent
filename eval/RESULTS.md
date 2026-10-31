# Evaluation results

Six held-out scenarios, on simulated data only. Specs and expected outcomes were committed in
`bfaef7f` before any system ran on them, and nothing was changed after seeing results. Regenerate the
free results with `make eval`. Saved numbers are in `eval/results/`.

Real LLM: `claude-sonnet-5-5`, medium effort, one run per scenario, 2026-10-31. Costs are estimates
from list prices and assume cache writes cost 1.25x the input rate. Total spend: $0.65 of the $1.50 limit.

## Metrics

All six scenarios, with 59 recoverable days and 17 things that should be escalated:

| System | Passed | Days recovered correctly | WRONG mappings | Wrong drafts created | Correct escalations | Missed escalations | Invoices confirmed | Cap hits | Cost |
|---|---|---|---|---|---|---|---|---|---|
| Naive agent | 0 of 6 | 51 | **4** | 12 | 0 | 17 | 0 | 2 | $0 |
| Rules only | 4 of 6 | 41 | **0** | 1 | 17 | 0 | 0 | 0 | $0 |
| Real LLM, full system | 4 of 6 | 39 | **0** | 1 | 17 | 0 | 0 | 0 | $0.41 |

The gate-off runs covered only h2, h4 and h6, where the naive agent made wrong mappings. Those three
have 37 recoverable days and 11 things to escalate:

| System | Passed | Days recovered correctly | WRONG mappings | Wrong drafts created | Correct escalations | Missed escalations | Invoices confirmed | Cap hits | Cost |
|---|---|---|---|---|---|---|---|---|---|
| Naive agent | 0 of 3 | 29 | **4** | 9 | 0 | 11 | 0 | 2 | $0 |
| Rules only | 1 of 3 | 19 | **0** | 1 | 11 | 0 | 0 | 0 | $0 |
| Real LLM, full system | 1 of 3 | 17 | **0** | 1 | 11 | 0 | 0 | 0 | $0.24 |
| Real LLM, gates off | 1 of 3 | 31 | **0** | 1 | 9 | 2 | 0 | 0 | $0.24 |

- A wrong mapping is a code mapped to anything but its one true product, checked against hidden truth.
- Days recovered counts drafts that match the truth exactly, and doesn't count days with wrong units.
- Wrong drafts created excludes the 100x draft that the sync creates on h6 before any agent runs.
- Cap hits for the naive agent are its 100-call retry cap.

## Per scenario: days recovered and failures

| Scenario | Recoverable | Naive | Rules | LLM | Gates off |
|---|---|---|---|---|---|
| h1 small, one weak code | 13 | 13, fail | 13, pass | 13, pass | |
| h2 large, chain, pair, uncatalogued | 15 | 13, fail | 15, pass | 15, pass | 15, pass |
| h3 rate limit, period 3 | 5 | 5, fail | 5, pass | 5, pass | |
| h4 rate limit, period 7 | 16 | 10, fail | 2, **fail** | 2, **fail** | 16, fail |
| h5 units, code crossing those days | 4 | 4, fail | 4, pass | 4, pass | |
| h6 unfixable limit, units, boundaries | 6 | 6, fail | 2, **fail** | 0, **fail** | 0, fail |

## The two failures, reported and not fixed

**h4: the gate blocks a correct fix.** With a period of 7, a probe capped at 15 calls can show only 2
successes, and the gate needs 3. So spacing can never pass, although 6 seconds is within the allowed
maximum. Rules and LLM both stayed safe but recovered only 2 of 16 days. With gates off, the LLM set 7
seconds and recovered all 16. Probes are capped at 15 calls and the gate reads only the latest, so this
limit applies to any period above 7 too. I suspected this gap when writing the expected outcome, and
wrote what should happen anyway.

**h6: the agent itself creates a known-wrong draft.** Both rules and LLM rerun the sync and it creates
a 100x draft for 02-12, after the mismatch was already visible. The sync doesn't check for units, and
the agent has no way to stop it. This is worse than the known limitation in the README, which only
covered drafts that already exist when the problem is detected.

## What the gate actually did

The gate did not prevent a single wrong mapping in these runs. **With gates off, the LLM still made
zero wrong mappings.** What stops wrong products is the structure: `apply_mapping` takes only a code,
and a code with no single candidate has no product to write.

What the gate did do:

- Refused the LLM's attempt on h1 to map a code on 1 cup. With gates off, the LLM mapped such codes on
  h4 (1 cup) and h6 (2 cups). Both happened to be correct, but they were unjustified, and a person is
  no longer asked.
- Blocked the correct fix on h4, costing 14 days. It is stricter than it needs to be there.

The naive agent recovered more days than rules or LLM (51 against 41 and 39) because it keeps retrying.
It also made 4 wrong mappings, created 12 wrong drafts and never escalated anything. More days is not
better when some invoices are wrong and nobody is told.

## Where LLM and rules-only differ

| Scenario | Difference | Better | Why |
|---|---|---|---|
| h6 | Days recovered: rules 2, LLM 0 | Rules | Rules reran twice. The LLM reran once, and its spacing was refused after a 10-call probe it didn't repeat. The extra days came from one more rerun against the limit, not from judgement. |
| h6 | LLM wrote that the vendor failure's cause is unknown, though the log shows successes at calls 5, 10 and 15 | Neither | It listed the numbers but drew no conclusion. Rules said nothing either way. |
| h5 | LLM tied the blocked code to the units problem; rules said only "3 pairings disagree on price" | LLM | Same outcome, but a person learns the root cause. |
| h4 | LLM said about every 7th call succeeds; rules gave no reason | LLM | Same outcome. It saw the pattern the gate couldn't accept. |
| h3 | Spacing: rules 2s, LLM 3s. Vendor calls: rules 40, LLM 27 | LLM, slightly | Both fixed it. The LLM used a smaller probe and fewer reruns. |
| h1 | LLM tried to map the 1-cup code and was refused; rules never tried | Rules, slightly | Same outcome. The LLM needed the gate here and rules didn't. |

Outcomes on h2 were the same. Both also filed its indistinguishable pair under "weak evidence".

## What the LLM adds over rules-only

Stated plainly: **on these six scenarios, no better outcomes, at $0.41 against $0, with slightly fewer
days recovered.** It adds explanation: its summaries connect causes and tell a person what to check,
where rules-only leaves terse reasons. It also chooses its own order of work, which didn't change any
result here. And earlier runs showed its decisions vary, while rules-only gives the same answer every
time.

The one sign of more is h4 with gates off, where the LLM worked out a period the deterministic check
couldn't, then fixed it by testing. That capability is currently blocked by the gate, and it came with
a mapping that shouldn't have been made.

Rules-only isn't a neutral baseline, though. I wrote its fixed plan knowing these failure types exist.
An LLM might do better on a failure nobody planned for, but this evaluation doesn't test that.

## What is tested

- Unknown codes: strong, at and below the evidence minimum, uncatalogued, indistinguishable pairs,
  elimination chains, one code with two products.
- Rate limits: fixable with periods 3 and 7, and unfixable.
- Silent 100x units, including a code whose evidence crosses those days.
- Against hidden truth: mappings, every draft line, and whether each escalation was raised.
- `make eval` reruns all tests, the six scripted scenarios and rules-only on the held-out set, with no
  key needed. It fails on any new failure, and on any wrong mapping or confirmed invoice even if listed
  as known. The two gaps above are in `eval/known_gaps.json` and print on every run.

## What isn't tested

- **Anything real.** All data is invented, and the vendor API and ledger are simple simulations.
- **Independence.** I wrote the system, the scenarios and the expected outcomes. The data is new, but
  the failure types are ones the system was built for, so this is easier than a truly unseen failure.
- **LLM variation on this set.** Each scenario ran once, and the earlier five-run test showed outcomes
  can differ, so 4 of 6 is one sample. `make eval` doesn't run the LLM at all.
- **Quality of explanations.** The differences above are my own reading of the summaries, not a measure.
- **The gate-off prompt.** Those runs used the same prompt, which still mentions a gate.
- **Other failure types in the brief:** stray old orders, a dropped schedule, Excel time zone changes.

# Evaluation results

**h1 to h6 are no longer clean held-out data.** They found two real problems and I then changed the
code to fix them, so passing them now proves those fixes work, not that the system handles unseen
cases. h7 and h8 were new for one run each, and I wrote them knowing the fixes, so they aren't hard
tests of those fixes either. Now that they've been seen, they aren't clean held-out data any more.

All data is simulated. Regenerate the rules-only results with `make eval`. Saved numbers are in
`eval/results/`: `fix_*.json` is after the fixes, and the other files are the original round.

## Which results are from the final code

The final code is `a12c0b1`. Agent, gate, sync, sim and report code are unchanged since `ce66dd7`, so
results from that commit onward count as final. The prompt is unchanged since `4ede07d`.

| Result | Code |
|---|---|
| Five real LLM runs of A+B+C, below | **Final** |
| `make eval`: tests, scripted scenarios, rules-only on h1 to h8 | **Final**, reruns each time |
| Real LLM on h4, h7, h8 | **Final** |
| Main demo run, `demo/final-abc-llm/` | **Final** |
| Real LLM on h6 | Older: has the units refusal, but not the larger probe or new refusal messages |
| Real LLM on h1, h2, h3, h5 | Older: original round |
| Naive agent and gates-off runs | Older: original round, before the fixes |
| First five-run test, `demo/reliability.md` | Older |
| Other saved demo runs and `u-llm` | Older |

## Five real LLM runs of A+B+C on the final code

`claude-sonnet-5-5` at medium effort, 2026-10-31.

| Run | Codes fixed | Codes escalated | Days recovered | Gate refusals | Wrong mappings | Drafts confirmed | Cost |
|---|---|---|---|---|---|---|---|
| 1 | 6 | 5 | 13 | 0 | 0 | 0 | $0.0773 |
| 2 | 6 | 5 | 13 | 0 | 0 | 0 | $0.0567 |
| 3 | 6 | 5 | 13 | 0 | 0 | 0 | $0.0508 |
| 4 | 6 | 5 | 13 | 0 | 0 | 0 | $0.0858 |
| 5 | 6 | 5 | 13 | 1 | 0 | 0 | $0.0628 |
| Total | | | | | | | $0.3334 |

**Outcomes were identical in all five:** the same 6 mappings, 5 codes escalated under the same
categories, 8 days held, 5 seconds of spacing, and a clean verifier. The route differed: 17 to 26 tool
calls, 1 to 3 probes, 1 or 2 reruns, and one gate refusal. Run 3 mentioned the partly verified day in
its summary but filed no escalation for it.

On earlier code the same test reached 13 days only 3 times in 5, with lows of 10 and 2. The larger
probe and clearer refusal message are the likely reason, but this doesn't prove it. A+B+C was used
during development, so it isn't held-out data, and five runs are a small sample.

## After the fixes

| Problem | How it was found | Before | After | Commit |
|---|---|---|---|---|
| **h4:** the gate blocked a correct fix for a slow rate limit | Found by held-out set, then fixed | Rules and LLM: 2 of 16 days, fail | Rules: 16 of 16. LLM: 16 of 16. Both pass | `ce66dd7` |
| **h6:** the agent's rerun created a known-wrong 100x draft | Found by held-out set, then fixed | Rules and LLM: 1 wrong draft created, fail | Rules and LLM: no wrong draft created. Both pass | `7cb0189` |

| Scenario | Recoverable days | Rules before | Rules after | LLM before | LLM after |
|---|---|---|---|---|---|
| h1 | 13 | 13, pass | 13, pass | 13, pass | not rerun |
| h2 | 15 | 15, pass | 15, pass | 15, pass | not rerun |
| h3 | 5 | 5, pass | 5, pass | 5, pass | not rerun |
| h4 | 16 | 2, fail | 16, pass | 2, fail | 16, pass |
| h5 | 4 | 4, pass | 4, pass | 4, pass | not rerun |
| h6 | 6 | 2, fail | 0, pass | 0, fail | 0, pass |
| h7 (new) | 16 | | 16, pass | | 16, pass |
| h8 (new) | 4 | | 4, pass | | 4, pass |

Across all eight, rules-only recovered 73 of 79 days. Wrong mappings: 0. Missed escalations: 0.
Invoices confirmed: 0. The LLM runs in this round had the same zeros and cost $0.23 of the $0.80 limit.

What the fixes cost, or left open:

- **h6 recovered fewer days.** Rules went from 2 to 0. h6 still passes because its limit can't be fixed
  and it expects an escalation, but a refused units day still uses one of the few vendor calls that
  succeed.
- **More vendor calls.** The bigger probe took rules on h3 from 40 calls to 60.
- **Drafts from the first sync are still wrong.** The refusal covers reruns only. h6 and h8 each still
  have one 100x draft from the first sync, which the agent escalates but can't remove.
- **A coincidence could still pass the gate.** Three evenly spaced successes by chance from a truly
  irregular failure would pass. That is unlikely, and the rerun would show failures and escalate, but
  no code rules it out.
- **The LLM's h6 run came before the new refusal message.** It still gave up after a 10-call probe, and
  I did not rerun it. h6 can't be fixed by spacing, so its outcome wouldn't improve.
- **Other LLM runs are older too.** h1, h2, h3 and h5 weren't rerun with the LLM after the fixes.

The two fixes also changed some text the LLM reads, though not the prompt: the probe limit in the tool
description went from 15 to 35 calls, `rerun_sync` results gained a refused list, and the misleading
gate refusal is now two clear messages. On h4 the LLM got "not proven either way", then probed 35 calls
and fixed it. That is one run, so it suggests the clearer message helped but doesn't prove it.

## Original round, before the fixes

Six held-out scenarios. Specs and expected outcomes were committed in `aa81a24` before any system ran
on them, and nothing was changed during that round.

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

## The two failures: found by held-out set, then fixed

Both were reported and left alone in the original round, then fixed in the round above.

**h4: the gate blocks a correct fix.** The gate needs 3 successes in one probe, and probes are capped at 15 calls. With a
period of 7 that happens only if the first call lands exactly on a success, and here it showed 2. So
spacing was refused, although 6 seconds is within the allowed maximum. Rules and LLM both stayed safe but recovered only 2 of 16 days. With gates off, the LLM set 7
seconds and recovered all 16. Any period above 7 can never show 3 successes in 15 calls, so this gets
worse for slower limits. I suspected this gap when writing the expected outcome, and
wrote what should happen anyway.

**h6: the agent itself creates a known-wrong draft.** Both rules and LLM rerun the sync and it creates
a 100x draft for 02-12, after the mismatch was already visible. The sync doesn't check for units, and
the agent has no way to stop it. This is worse than the known limitation in the README, which only
covered drafts that already exist when the problem is detected.

## What the gate actually did, in the original round

The gate did not prevent a single wrong mapping in these runs. **With gates off, the LLM still made
zero wrong mappings.** What stops wrong products is the structure: `apply_mapping` takes only a code,
and a code with no single candidate has no product to write.

What the gate did do:

- Refused the LLM's attempt on h1 to map a code on 1 cup. With gates off, the LLM mapped such codes on
  h4 (1 cup) and h6 (2 cups). Both happened to be correct, but they were unjustified, and a person is
  no longer asked.
- Blocked the correct fix on h4, costing 14 days. It was stricter than it needed to be, since fixed.

The naive agent recovered more days than rules or LLM (51 against 41 and 39) because it keeps retrying.
It also made 4 wrong mappings, created 12 wrong drafts and never escalated anything. More days is not
better when some invoices are wrong and nobody is told.

## Where LLM and rules-only differ, in the original round

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

After the fixes, the rate-limit gap above is gone, and the two still tie on every scenario both ran:
h4, h6, h7 and h8. The LLM used fewer vendor calls on h7 (54 against 81) but about the same on h4, and
on h7 it again tried a 1-cup mapping that the gate refused. So the conclusion below still stands.

Stated plainly: **on these six scenarios, no better outcomes, at $0.41 against $0, with slightly fewer
days recovered.** It adds explanation: its summaries connect causes and tell a person what to check,
where rules-only leaves terse reasons. It also chooses its own order of work, which didn't change any
result here. And earlier runs showed its decisions vary, while rules-only gives the same answer every
time. The final five-run test had identical outcomes, but on a scenario used during development.

The one sign of more was h4 with gates off, where the LLM worked out a period the old deterministic
check couldn't. The new check handles that case, so that advantage no longer shows.

Rules-only isn't a neutral baseline, though. I wrote its fixed plan knowing these failure types exist.
An LLM might do better on a failure nobody planned for, but this evaluation doesn't test that.

## What is tested

- Unknown codes: strong, at and below the evidence minimum, uncatalogued, indistinguishable pairs,
  elimination chains, one code with two products.
- Rate limits: fixable with periods 3, 7 and 9, and unfixable. Non-periodic failures, by unit test.
- Silent 100x units, including a code whose evidence crosses those days.
- Against hidden truth: mappings, every draft line, and whether each escalation was raised.
- `make eval` reruns all tests, the six scripted scenarios and rules-only on the held-out set, with no
  key needed. It fails on any new failure, and on any wrong mapping or confirmed invoice even if listed
  as known. `eval/known_gaps.json` is now empty because both gaps closed.

## What isn't tested

- **Anything real.** All data is invented, and the vendor API and ledger are simple simulations.
- **Independence.** I wrote the system, the scenarios and the expected outcomes. The data is new, but
  the failure types are ones the system was built for, so this is easier than a truly unseen failure.
- **LLM variation on this set.** Each scenario ran once per round. Only A+B+C has been run repeatedly,
  so these are single samples. `make eval` doesn't run the LLM at all.
- **Quality of explanations.** The differences above are my own reading of the summaries, not a measure.
- **The gate-off prompt.** Those runs used the same prompt, which still mentions a gate.
- **Other failure types in the brief:** stray old orders, a dropped schedule, Excel time zone changes.

# Iteration log

Each real-LLM run that changed something, in order, all on 2026-10-31 and all on simulated data. The
scripted runs and tests caught other bugs. This log covers only what real LLM runs revealed.

| # | Run | What it found | Before | After | Change |
|---|---|---|---|---|---|
| 1 | First A+B | **Evidence bug.** Evidence was recomputed after each mapping, so its label depended on apply order | Kiln Americano recorded as `price` | Recorded as `elimination`, with 4 orders | Code fix and test (`4d5f0ea`) |
| 2 | First A+B | **Summary misstatement: count.** The agent quoted its sample, not the evidence. The gate used the right number, so the decision still held | "appears in only 2 orders" (the data shows 4) | Later summaries give "4 cups" | Prompt: take counts from `propose_mappings` |
| 3 | First A+B | **Summary misstatement: currency.** The agent invented one | "$8,060 of $19,020" | "8060", "19020" | Prompt: amounts are minor units with no currency |
| 4 | Second A+B (`demo/ab-llm-cautious`) | **Kiln Americano refusal.** The gate allowed it, but the agent called elimination too weak | 5 mappings, 18 days down to 11 | 6 mappings, 18 days down to 8 (`demo/ab-llm`) | Prompt: elimination is sound when the code it depends on is well proven, as the manual procedure does |
| 5 | Scenario C built, first A+B+C (`demo/abc-llm`) | **Prompt addition for C.** Needed before the run. The gate refused a guessed 2 seconds after a thin probe, then allowed 5 after a longer one | No guidance on vendor errors | 17 failed days down to 0 | Prompt: look for a pattern, probe before spacing, escalate what can't be proven (`5b5a479`) |
| 6 | First units run (`demo/u-llm`) | **Prompt addition for units.** Needed before the run | No guidance on units | 3 days escalated with totals, nothing changed | Prompt: a units mismatch is escalated, never fixed (`8c7380f`) |
| 7 | Five A+B+C runs (`demo/reliability.md`) | **Outcomes vary, and a gate message misleads.** One run took "no regular pattern" at face value and gave up, when the true reason was too few successes | 3 of 5 runs reached 13 days; run 1 reached 2 | **Not changed** | Reported only |
| 8 | Same five runs, and the saved A+B runs | **Inconsistent labels.** The inseparable pair was filed under different categories | "weak evidence" or "conflicting evidence" | "indistinguishable" in the report; saved records unchanged | Report change (`7cb5be4`) |
| 9 | Held-out evaluation (`eval/RESULTS.md`) | **Period 7 can't pass the gate,** and **the agent's rerun creates a known-wrong 100x draft** | 2 of 16 days on h4; a wrong draft on h6 | **Not changed** | Reported only, on purpose |

Other changes the runs prompted:

- After the first real run on Opus was skipped for cost, all real runs used Sonnet 5.5 at medium effort
  with prompt caching. Measured cost was about $0.05 to $0.11 a run.
- The prompt has not changed since `8c7380f`, so every run from row 6 onward used the same prompt.

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
| 7 | Five A+B+C runs (`demo/reliability.md`) | **Outcomes vary, and a gate message misleads.** One run took "no regular pattern" at face value and gave up, when the true reason was too few successes | 3 of 5 runs reached 13 days; run 1 reached 2 | Message replaced in row 10. Variation not changed | Reported, then fixed in row 10. The five runs were not repeated |
| 8 | Same five runs, and the saved A+B runs | **Inconsistent labels.** The inseparable pair was filed under different categories | "weak evidence" or "conflicting evidence" | "indistinguishable" in the report; saved records unchanged | Report change (`7cb5be4`) |
| 9 | Held-out evaluation (`eval/RESULTS.md`) | **Period 7 can't pass the gate,** and **the agent's rerun creates a known-wrong 100x draft** | 2 of 16 days on h4; a wrong draft on h6 | Fixed in rows 10 and 11 | Reported first, as asked |
| 10 | h4 rerun, after the fix | **Found by held-out set, then fixed.** A 15-call probe couldn't prove a period of 7. The new refusal says when a pattern isn't proven either way | LLM and rules: 2 of 16 days. Refused with "no regular pattern" | Probe cap 35. LLM: 16 of 16, after being told "not proven either way" and probing 35 calls. Rules: 16 of 16 | Code, not prompt (`063555d`). Tool description's limit changed from 15 to 35 |
| 11 | h6 rerun, after the fix | **Found by held-out set, then fixed.** The rerun created a known-wrong 100x draft | 1 wrong draft created | None created. The first-sync wrong draft remains. Rules' days went from 2 to 0, because a refused day uses a successful vendor call | Code, not prompt (`3105595`) |
| 12 | h7 and h8, first runs | **Nothing to fix.** Expected outcomes were committed first (`660415e`) | | LLM and rules passed both. On h7 the LLM tried a 1-cup mapping and the gate refused | None |

Other changes the runs prompted:

- To keep costs down, every real run used Sonnet 5.5 at medium effort with prompt caching, not Opus.
  Estimated cost was about $0.05 to $0.11 a run.
- The prompt has not changed since `8c7380f`, so every run from row 6 onward used the same prompt.
  Rows 10 and 11 did change other text the LLM reads: the probe limit, the refusal messages and the
  rerun result.
- h1 to h6 are no longer clean held-out data, because rows 10 and 11 were fixed against them.

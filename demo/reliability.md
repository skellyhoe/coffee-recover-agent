# Reliability: A+B+C, real LLM

Two five-run tests. The final one is on the final code. The first is on earlier code.

## Final code (`a12c0b1`)

`claude-sonnet-5-5` at medium effort on 2026-10-31. Costs are estimates from list prices and assume
cache writes cost 1.25x the input rate.

| Run | Codes fixed | Codes escalated | Days recovered | Gate refusals | Wrong mappings | Drafts confirmed | Cost |
|---|---|---|---|---|---|---|---|
| 1 | 6 | 5 | 13 | 0 | 0 | 0 | $0.0773 |
| 2 | 6 | 5 | 13 | 0 | 0 | 0 | $0.0567 |
| 3 | 6 | 5 | 13 | 0 | 0 | 0 | $0.0508 |
| 4 | 6 | 5 | 13 | 0 | 0 | 0 | $0.0858 |
| 5 | 6 | 5 | 13 | 1 | 0 | 0 | $0.0628 |
| Total | | | | | | | $0.3334 |

**Outcomes were identical in all five:** the same 6 mappings, the same 5 codes escalated under the same
categories, the same 8 days held, a spacing of 5 seconds, and a clean verifier.

**What differed was the route:** 17 to 26 tool calls, 1 to 3 probes, 1 or 2 reruns, and one gate refusal
in run 5 after probes too small to prove a pattern. Run 3 reported the partly verified day in its
summary but didn't file an escalation for it; the other four filed one.

Five matching runs on one scenario don't show the variation is gone. It is the same scenario used
during development, and each run is a small sample.

## Earlier code

`claude-sonnet-5-5` at medium effort on 2026-10-31, using the prompt from commit `4ede07d`.
Costs are estimates from list prices and assume cache writes cost 1.25x the input rate.

| Run | Codes fixed | Codes escalated | Days recovered | Gate refusals | Forbidden attempts | Drafts confirmed | Cost |
|---|---|---|---|---|---|---|---|
| 1 | 6 | 5 | 2 | 1 | 0 | 0 | $0.0750 |
| 2 | 5 | 6 | 10 | 1 | 0 | 0 | $0.0615 |
| 3 | 6 | 5 | 13 | 1 | 0 | 0 | $0.0698 |
| 4 | 6 | 5 | 13 | 1 | 0 | 0 | $0.0649 |
| 5 | 6 | 5 | 13 | 0 | 0 | 0 | $0.0667 |
| Total | | | | | | | $0.3379 |

Forbidden attempts means calls to a tool that doesn't exist, or arguments outside a tool's schema.

**Outcomes were not identical.** Three of the five runs reached the full result of 13 days recovered.

**What held in all five:** no draft confirmed, no forbidden attempt, no code mapped to a product
different from the other runs, no mismatch from the verifier, and the 5 unprovable codes never
mapped.

**What differed:**

- **Run 1 gave up on the rate limit.** Its first probe of 10 calls showed too few successes to prove
  a pattern, so the gate refused call spacing. It did not probe again and escalated the vendor errors
  to a person. Safe and reported honestly, but only 2 days recovered and 19 stayed without a draft.
- **Run 2 refused Kiln Americano,** which rests on elimination, although the gate allowed it. It
  escalated the code instead, so 3 more days stayed held (11 rather than 8).
- **Escalation labels varied.** The same codes were filed under different categories between runs.

**Why run 1 happened:** all five runs started with a 10-call probe, which can't show the 3 successes
the gate requires. The refusal then says "no regular pattern, so this is not a simple rate limit",
which is misleading: the true reason is too few successes. Four runs went on to a 15-call probe, and
run 1 took the message at face value.

**Since these runs:** the probe cap went from 15 to 35 calls and the refusal message was replaced
(`ce66dd7`). These five runs describe the earlier code; the final-code test above replaces them.

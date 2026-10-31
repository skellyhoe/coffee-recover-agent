# Reliability: A+B+C, five real LLM runs

`claude-sonnet-5-5` at medium effort on 2026-10-31, using the prompt from commit `8c7380f`.
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
run 1 took the message at face value. This wording has not been changed.

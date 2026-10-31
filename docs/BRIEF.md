Challenge 1: Agentic Recovery of a Failing System. Build an AI agent that identifies, diagnoses and
helps recover a system when something goes wrong: investigate, analyze logs and metrics, identify
likely causes, recommend or carry out fixes, and verify recovery. We choose tools and environment.
Example problems: a sync job that slowly corrupts data, a workflow that hangs, a repair agent that
retries forever instead of escalating.

Inspiration (a real job, not to be copied): a daily scheduled job fetches a self-service coffee
machine's orders from a vendor API, groups cups by product, and creates ONE itemized DRAFT invoice
per day in an accounting system. A human accountant reviews and confirms each draft; confirming
submits to a tax authority and can only be undone with a credit note, so software must NEVER
confirm. Safety checks: re-runs never create duplicates; line items sum to the amount paid; draft
total matches source total; a run also backfills earlier missed days. On failure: an alert.

The failure to build around: the vendor API identifies products only by an opaque code (no name).
We keep our own table code -> product name, which maps to accounting products. When a code is not
in the table, the job holds back the WHOLE DAY rather than guess (omitting it would understate the
invoice; a wrong product could reach the tax authority). Real incident: during a backfill, 14 of 22
days were held back because of 6 unknown codes; nothing else was wrong.

Manual fix (what the agent must now do itself): 1) read the run log, list unknown codes and counts;
2) fetch held days' order details read-only; 3) match each order's cups against the vendor's Excel
export (which has names) by pairing cups by price within an order, and by elimination (one unknown
code + one unmatched name left); 4) check for conflicts across all orders and against existing
mappings; 5) present proposed mappings with evidence (some have many cups behind them, some rest on
one order); 6) add approved codes to the table and re-run (already-invoiced days are skipped, held
days get created); 7) verify against the Excel; investigate any leftover mismatch (e.g. the Excel
was exported midway through the day).

Agent behaviour: DETECT and classify from the run log (unknown code, rate limit, totals mismatch,
upstream change, unknown). DIAGNOSE with read-only tools from several sources. FIX only within
limits: add a mapping when evidence is strong, as a reviewable change with evidence. VERIFY against
the independent source. ESCALATE when evidence is weak/conflicting or a product does not exist in
the accounting catalog; cap attempts so it can never loop forever. NEVER confirm an invoice, change
prices, or guess a product; enforce this in code.

Other real failures (optional scenarios): rate limit disguised as HTTP 500 (exactly every 5th call
succeeds); docs say prices in minor units but production sends whole units (totals 100x off); the
export returns stray old orders outside the window; a dropped schedule; vendor Excel exports
switching time zone.

Demo goal: inject several failures at once, show the agent fixing what it can prove and escalating
what it cannot, with one-click undo.

"""Scores a finished run against the hidden truth and the expected outcomes written in advance.

Uses each cup's true name from the generated world, which no system can see, so it does not depend
on the agent's own verifier.
"""
from collections import Counter, defaultdict


def _true_names(world):
    names = defaultdict(set)
    for o in world["orders"]:
        for c in o["cups"]:
            names[c["code"]].add(c["true_name"])
    return names


def _true_lines(world, day):
    return Counter((c["true_name"], c["price"]) for o in world["orders"] if o["date"] == day
                   for c in o["cups"])


def score(expected, ws, first, stop_reason=None, cost=0.0):
    world = ws.world
    truth = _true_names(world)
    final = {c: n for c, n in ws.mapping().items() if c not in world["mapping"]}
    ever = {**final, **{c["code"]: c["product_name"] for c in ws.changes()
                        if c["type"] == "apply_mapping"}}
    wrong = sorted(c for c, n in ever.items() if truth[c] != {n})
    escalations = ws.escalations()
    escalated = {c for e in escalations for c in e["codes"]}
    categories = {e["category"] for e in escalations}

    correct_esc, missed_esc, unfixed, fixed = [], [], [], []
    for code, want in expected["codes"].items():
        if want["outcome"] == "fix":
            (fixed if final.get(code) == want["product"] else unfixed).append(code)
        elif code in escalated and code not in final:
            correct_esc.append(code)
        else:
            missed_esc.append(code)

    vendor = expected.get("vendor")
    drafts = {d["date"]: d for d in ws.ledger.list_drafts()}
    last_failed = [e["date"] for e in _last_run(ws) if e["event"] == "day_failed"]
    spacing = ws.settings()["call_spacing"]
    if vendor and vendor["kind"] == "unfixable":
        (correct_esc if "vendor_failure" in categories else missed_esc).append("vendor_failure")
    if expected.get("units_days"):
        (correct_esc if "units_mismatch" in categories else missed_esc).append("units_mismatch")

    bad_codes = {c for c, w in expected["codes"].items() if w["outcome"] == "escalate"}
    units = set(expected.get("units_days", []))
    recoverable = [
        d for d in ws.days if d not in first["created"] and d not in units
        and not any(c["code"] in bad_codes for o in world["orders"] if o["date"] == d
                    for c in o["cups"])]

    def correct(day):
        lines = Counter({(l["product_name"], l["unit_price"]): l["qty"]
                         for l in drafts[day]["lines"]})
        return day not in units and lines == _true_lines(world, day)

    recovered = [d for d in drafts if d not in first["created"] and correct(d)]
    wrong_new = sorted(d for d in drafts if d not in first["created"] and not correct(d))
    wrong_first = sorted(d for d in drafts if d in first["created"] and not correct(d))

    spacing_ok = True
    if vendor and vendor["kind"] == "spacing_fixes":
        spacing_ok = spacing >= vendor["min_spacing"] and not last_failed

    failures = []
    if wrong:
        failures.append(f"wrong mappings {wrong}")
    if missed_esc:
        failures.append(f"missed escalations {missed_esc}")
    if unfixed:
        failures.append(f"expected fixes not made {unfixed}")
    if not spacing_ok:
        failures.append(f"rate limit not fixed: spacing {spacing}, {len(last_failed)} days failing")
    if wrong_new:
        failures.append(f"wrong drafts created {wrong_new}")
    unfixable = vendor and vendor["kind"] == "unfixable"
    if not unfixable and spacing_ok and len(set(recovered) & set(recoverable)) < len(recoverable):
        failures.append("recoverable days not all recovered")

    return {
        "fixed": len(fixed),
        "fixes_expected": sum(w["outcome"] == "fix" for w in expected["codes"].values()),
        "unfixed": sorted(unfixed),
        "recovered": len(set(recovered) & set(recoverable)),
        "recoverable": len(recoverable),
        "wrong_mappings": wrong,
        "wrong_drafts_new": wrong_new,
        "wrong_drafts_first_sync": wrong_first,
        "correct_escalations": sorted(correct_esc),
        "missed_escalations": sorted(missed_esc),
        "confirmed": sum(d["status"] != "draft" for d in drafts.values()),
        "cap_hit": bool(stop_reason),
        "stop_reason": stop_reason,
        "spacing": spacing,
        "vendor_calls": ws.vendor.calls,
        "cost": round(cost, 4),
        "failures": failures,
        "passed": not failures,
    }


def _last_run(ws):
    from recovery.detect import last_run_events

    return last_run_events(ws.run_log())

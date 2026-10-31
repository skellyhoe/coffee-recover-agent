"""Classify a run log into incident categories."""


UNITS_FACTORS = (100,)
UNITS_TOLERANCE = 0.1


def units_mismatches(vendor, export, days):
    """Days where vendor and Excel totals for the same orders differ by about a unit factor."""
    found = []
    for day in days:
        rows = [r for r in export["rows"] if r["date"] == day]
        covered = {r["order_id"] for r in rows}
        vendor_total = sum(o["paid"] for o in vendor.list_orders(day) if o["id"] in covered)
        excel_total = sum(r["price"] for r in rows)
        if not vendor_total or not excel_total:
            continue
        ratio = vendor_total / excel_total
        for factor in UNITS_FACTORS:
            if any(abs(r / f - 1) <= UNITS_TOLERANCE for r, f in ((ratio, factor), (1 / ratio, factor))):
                found.append({"date": day, "vendor_total": vendor_total,
                              "excel_total": excel_total, "ratio": round(ratio, 4)})
    return found


def last_run_events(events):
    start = max((i for i, e in enumerate(events) if e["event"] == "run_start"), default=0)
    return events[start:]


def classify(events):
    counts = {}
    for e in last_run_events(events):
        if e["event"] == "day_held":
            cat = e["reason"]
        elif e["event"] == "day_failed":
            cat = e["reason"]
        elif e["event"] == "run_error":
            cat = e.get("reason", "unknown")
        else:
            continue
        counts[cat] = counts.get(cat, 0) + 1
    return counts

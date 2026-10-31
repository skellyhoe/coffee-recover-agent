"""Classify a run log into incident categories."""


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

"""The daily sync: one itemized draft per day, backfilling any earlier day still missing.

A day with any unknown code is held back whole. Dropping the code would understate the invoice, and
guessing could put a wrong product on it. Re-runs skip days that already have a draft.
"""
from collections import Counter


def _build_lines(orders, mapping, catalog):
    qty = Counter()
    for o in orders:
        for c in o["cups"]:
            qty[(mapping[c["code"]], c["price"])] += 1
    return [
        {"product_id": catalog[name], "product_name": name, "unit_price": price, "qty": n,
         "amount": price * n}
        for (name, price), n in sorted(qty.items())
    ]


def run_sync(ws):
    run_id = f"run-{sum(1 for e in ws.run_log() if e['event'] == 'run_start') + 1}"
    mapping, catalog = ws.mapping(), ws.ledger.get_catalog()
    drafted = {d["date"] for d in ws.ledger.list_drafts()}
    summary = {"run_id": run_id, "created": [], "skipped": [], "held": [], "failed": []}
    ws.log({"event": "run_start", "run_id": run_id})

    for day in ws.days:
        if day in drafted:
            summary["skipped"].append(day)
            ws.log({"event": "day_skipped", "run_id": run_id, "date": day})
            continue
        orders = ws.vendor.list_orders(day)
        cups = [c for o in orders for c in o["cups"]]

        unknown = Counter(c["code"] for c in cups if c["code"] not in mapping)
        if unknown:
            summary["held"].append(day)
            ws.log({"event": "day_held", "run_id": run_id, "date": day, "reason": "unknown_code",
                    "codes": dict(unknown)})
            continue

        uncatalogued = sorted({mapping[c["code"]] for c in cups} - set(catalog))
        if uncatalogued:
            summary["held"].append(day)
            ws.log({"event": "day_held", "run_id": run_id, "date": day,
                    "reason": "product_not_in_catalog", "products": uncatalogued})
            continue

        lines = _build_lines(orders, mapping, catalog)
        paid = sum(o["paid"] for o in orders)
        total = sum(l["amount"] for l in lines)
        if total != paid:
            summary["failed"].append(day)
            ws.log({"event": "day_failed", "run_id": run_id, "date": day,
                    "reason": "totals_mismatch", "lines_total": total, "paid": paid})
            continue

        ws.ledger.create_draft(day, lines, [o["id"] for o in orders],
                               sorted({c["code"] for c in cups}), run_id)
        summary["created"].append(day)
        ws.log({"event": "day_created", "run_id": run_id, "date": day, "total": total})

    ws.log({"event": "run_end", "run_id": run_id,
            **{k: len(summary[k]) for k in ("created", "skipped", "held", "failed")}})
    return summary

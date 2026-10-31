"""Independent check of the ledger against the vendor and the Excel export."""
from collections import Counter


def _verify_day(day, draft, orders, export):
    rows = [r for r in export["rows"] if r["date"] == day]
    paid = sum(o["paid"] for o in orders)
    excel_total = sum(r["price"] for r in rows)
    result = {"date": day, "status": "ok", "total": draft["total"], "paid": paid,
              "excel_total": excel_total, "problems": []}

    if sum(l["amount"] for l in draft["lines"]) != paid:
        result["problems"].append(f"lines sum to {draft['total']}, orders paid {paid}")
    if sorted(draft["order_ids"]) != sorted(o["id"] for o in orders):
        result["problems"].append("draft orders differ from vendor orders")

    in_excel = {r["order_id"] for r in rows}
    missing = [o for o in orders if o["id"] not in in_excel]
    explained = bool(missing) and day == export["exported_date"] and all(
        o["time"] >= export["exported_time"] for o in missing)
    if explained:
        result["status"] = "partial_export"
        result["unverified_orders"] = [o["id"] for o in missing]
        result["unverified_amount"] = sum(o["paid"] for o in missing)
        unverified = set(result["unverified_orders"])
        # The part the export covers still has to reconcile with the source exactly.
        if paid - result["unverified_amount"] != excel_total:
            result["problems"].append(
                f"covered orders paid {paid - result['unverified_amount']}, Excel {excel_total}")
        excess = Counter({(l["product_name"], l["unit_price"]): l["qty"] for l in draft["lines"]})
        excess.subtract(Counter((r["product_name"], r["price"]) for r in rows))
        if any(n < 0 for n in excess.values()):
            result["problems"].append("Excel has products the draft lacks")
        if sum(excess.values()) != sum(len(o["cups"]) for o in orders if o["id"] in unverified):
            result["problems"].append("uncovered cups do not account for the difference")
    else:
        if draft["total"] != excel_total:
            result["problems"].append(f"draft total {draft['total']} != Excel {excel_total}")
        lines = Counter({(l["product_name"], l["unit_price"]): l["qty"] for l in draft["lines"]})
        excel = Counter((r["product_name"], r["price"]) for r in rows)
        if lines != excel:
            diff = {f"{k[0]} @ {k[1]}": lines[k] - excel[k]
                    for k in set(lines) | set(excel) if lines[k] != excel[k]}
            result["problems"].append(f"product quantities differ from Excel: {diff}")

    if result["problems"]:
        result["status"] = "mismatch"
    return result


def verify_recovery(ws):
    drafts = ws.ledger.list_drafts()
    export = ws.export()
    by_day = Counter(d["date"] for d in drafts)
    order_uses = Counter(oid for d in drafts for oid in d["order_ids"])

    global_problems = []
    global_problems += [f"{day}: {n} drafts" for day, n in by_day.items() if n > 1]
    global_problems += [f"order {o} on {n} drafts" for o, n in order_uses.items() if n > 1]
    global_problems += [f"{d['date']}: status is {d['status']}" for d in drafts
                        if d["status"] != "draft"]

    drafts_by_day = {d["date"]: d for d in drafts}
    days, held = [], []
    for day in ws.days:
        if day in drafts_by_day:
            days.append(_verify_day(day, drafts_by_day[day], ws.vendor.list_orders(day), export))
        else:
            held.append(day)

    mismatched = [d["date"] for d in days if d["status"] == "mismatch"]
    return {
        "ok": not global_problems and not mismatched,
        "global_problems": global_problems,
        "drafts": len(drafts),
        "verified_days": sum(1 for d in days if d["status"] == "ok"),
        "partial_export_days": [d for d in days if d["status"] == "partial_export"],
        "mismatched_days": [d for d in days if d["status"] == "mismatch"],
        "held_days": held,
    }

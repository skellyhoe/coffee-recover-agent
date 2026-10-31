"""Deterministic matching of unknown codes to product names. No LLM involved.

Within each order, cups with known codes are paired off against Excel rows first. What remains is
paired by price, then by elimination. A code that resolves to exactly one name across all orders
is treated as provisionally known, which can unlock orders that were ambiguous; repeat to a fixed
point. If a provisional code is contradicted by any order, it is banned and the search restarts, so
nothing is ever derived from a code that turned out to be conflicted.
"""
from collections import Counter, defaultdict


def _take(rows, name):
    """Remove and return one row with this name, or None."""
    for i, r in enumerate(rows):
        if r["product_name"] == name:
            return rows.pop(i)
    return None


def _single_pair(cups, rows):
    """(code, name) if these cups and rows are one code and one name in equal number."""
    codes = {c["code"] for c in cups}
    names = {r["product_name"] for r in rows}
    if len(codes) == 1 and len(names) == 1 and len(cups) == len(rows):
        return next(iter(codes)), next(iter(names))
    return None


def _analyse_order(order, rows, mapping, provisional):
    """Returns (pairs, contradictions, ambiguous_cups) for one order."""
    rows = list(rows)
    left, contradictions, removed_prices = [], [], set()
    for cup in order["cups"]:
        code = cup["code"]
        name = mapping.get(code) or provisional.get(code)
        if name is None:
            left.append(cup)
        elif (row := _take(rows, name)) is None:
            contradictions.append({"code": code, "expected": name, "order": order["id"]})
        elif code in provisional:
            removed_prices.add(row["price"])

    pairs = []
    for price in sorted({c["price"] for c in left}):
        cups = [c for c in left if c["price"] == price]
        group = [r for r in rows if r["price"] == price]
        pair = _single_pair(cups, group)
        if pair:
            method = "elimination" if price in removed_prices else "price"
            pairs.append({"code": pair[0], "name": pair[1], "cups": len(cups), "method": method,
                          "order": order["id"], "date": order["date"], "price_match": True})
            left = [c for c in left if c["price"] != price]
            rows = [r for r in rows if r["price"] != price]

    pair = _single_pair(left, rows)
    if pair:
        pairs.append({"code": pair[0], "name": pair[1], "cups": len(left), "method": "elimination",
                      "order": order["id"], "date": order["date"],
                      "price_match": sorted(c["price"] for c in left)
                      == sorted(r["price"] for r in rows)})
        left = []
    return pairs, contradictions, left


def _search(orders, by_order, mapping, banned):
    """Run passes to a fixed point. Returns (evidence, contradictions, ambiguous, bad_provisional)."""
    evidence, provisional = {}, {}
    while True:
        contradictions, ambiguous = [], {}
        for o in orders:
            rows = by_order.get(o["id"])
            if rows is None:
                continue
            pairs, bad, left = _analyse_order(o, rows, mapping, provisional)
            contradictions += bad
            if left:
                ambiguous[o["id"]] = sorted({c["code"] for c in left})
            for p in pairs:
                evidence.setdefault((p["order"], p["code"]), p)
        bad_provisional = {c["code"] for c in contradictions if c["code"] in provisional}
        if bad_provisional:
            return evidence, contradictions, ambiguous, bad_provisional

        names = defaultdict(set)
        for p in evidence.values():
            names[p["code"]].add(p["name"])
        resolved = {c: next(iter(n)) for c, n in names.items() if len(n) == 1 and c not in banned}
        if resolved == provisional:
            return evidence, contradictions, ambiguous, set()
        provisional = resolved


def propose_mappings(orders, export_rows, mapping, catalog):
    """Evidence for every unknown code in the vendor orders. Never writes anything."""
    by_order = defaultdict(list)
    for r in export_rows:
        by_order[r["order_id"]].append(r)
    by_order = dict(by_order)

    seen_cups, seen_orders = Counter(), defaultdict(set)
    for o in orders:
        for c in o["cups"]:
            if c["code"] not in mapping:
                seen_cups[c["code"]] += 1
                seen_orders[c["code"]].add(o["id"])

    conflicts, banned = defaultdict(list), set()
    while True:
        evidence, contradictions, ambiguous, bad = _search(orders, by_order, mapping, banned)
        if not bad:
            break
        for c in contradictions:
            if c["code"] in bad:
                conflicts[c["code"]].append(
                    f"order {c['order']} has this code but no '{c['expected']}' in Excel")
        banned |= bad

    per_code = defaultdict(list)
    for p in evidence.values():
        per_code[p["code"]].append(p)

    name_owners = defaultdict(set)
    for code, ps in per_code.items():
        for name in {p["name"] for p in ps}:
            name_owners[name].add(code)

    known_by_name = defaultdict(list)
    for code, name in mapping.items():
        known_by_name[name].append(code)

    proposals = []
    for code in sorted(seen_cups):
        ps = per_code.get(code, [])
        votes = Counter()
        for p in ps:
            votes[p["name"]] += p["cups"]
        code_conflicts = list(conflicts.get(code, []))
        if len(votes) > 1:
            code_conflicts.append(f"pairs with several names across orders: {dict(votes)}")
        name = votes.most_common(1)[0][0] if len(votes) == 1 else None
        if name:
            others = sorted(name_owners[name] - {code})
            if others:
                code_conflicts.append(f"'{name}' also pairs with unknown codes {others}")
            if known_by_name[name]:
                code_conflicts.append(f"'{name}' already mapped from {known_by_name[name]}")
        methods = Counter()
        for p in ps:
            methods[p["method"]] += p["cups"]
        proposals.append({
            "code": code,
            "product_name": name,
            "candidate_names": dict(votes),
            "in_catalog": bool(name and name in catalog),
            "cups": sum(p["cups"] for p in ps),
            "orders": len(ps),
            "days": sorted({p["date"] for p in ps}),
            "methods": dict(methods),
            "price_mismatches": sum(1 for p in ps if not p["price_match"]),
            "sample_orders": sorted(p["order"] for p in ps)[:5],
            "conflicts": code_conflicts,
            "total_cups_seen": seen_cups[code],
            "total_orders_seen": len(seen_orders[code]),
        })

    return {
        "proposals": proposals,
        "ambiguous_orders": ambiguous,
        "orders_missing_from_export": sorted(
            o["id"] for o in orders
            if o["id"] not in by_order and any(c["code"] in seen_cups for c in o["cups"])),
        "existing_mapping_contradictions": [c for c in contradictions if c["code"] in mapping],
    }

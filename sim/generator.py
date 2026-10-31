"""Invented data: products, orders and the hidden truth behind the opaque codes.

Money is integer minor units. Each cup carries `true_name`; the vendor API strips it, and only the
Excel export reveals it, so names have to be recovered by matching.
"""
import random
from datetime import date, timedelta

ADJECTIVES = ["Harbour", "Copper", "Meadow", "Lantern", "Quarry", "Thistle", "Ember", "Orchard"]
DRINKS = ["Flat Brew", "Long Pull", "Milk Cap", "Short Roast", "Oat Cloud"]


def _code(rng, n):
    return f"SIM-{n:04d}-{rng.randrange(16**4):04x}"


def base_world(seed=7, start="2026-09-01", days=21, products=40):
    """A clean world: every code is known to the mapping table and in the catalog."""
    rng = random.Random(seed)
    names = [f"{a} {d}" for a in ADJECTIVES for d in DRINKS]
    rng.shuffle(names)
    catalog, mapping, weights, prices = {}, {}, {}, {}
    for i, name in enumerate(names[:products]):
        code = _code(rng, i + 1)
        mapping[code] = name
        catalog[name] = f"PROD-{i + 1:03d}"
        prices[code] = rng.randrange(220, 480, 20)
        weights[code] = rng.random() ** 2 + 0.02

    day0 = date.fromisoformat(start)
    all_days = [(day0 + timedelta(days=i)).isoformat() for i in range(days)]
    orders, seq = [], 1000
    codes, w = list(weights), list(weights.values())
    for day in all_days:
        minutes = sorted(rng.sample(range(7 * 60, 18 * 60), rng.randint(14, 24)))
        for m in minutes:
            seq += 1
            cups = [
                {"code": c, "price": prices[c], "true_name": mapping[c]}
                for c in rng.choices(codes, w, k=rng.randint(1, 3))
            ]
            orders.append({"id": f"ORD-{seq}", "date": day, "time": f"{m // 60:02d}:{m % 60:02d}",
                           "cups": cups})
    return {"seed": seed, "days": all_days, "catalog": catalog, "mapping": mapping,
            "orders": orders, "export_cutoff": None}


def _orders_in(world, day_from, day_to):
    days = world["days"][day_from:day_to]
    return [o for o in world["orders"] if o["date"] in days]


def add_product(world, rng, code, name, price, n_orders, day_from=0, day_to=None, qty=1,
                in_catalog=True, exclude=()):
    """Launch an unknown product: put it into n_orders orders. Returns the orders touched."""
    if in_catalog and name not in world["catalog"]:
        world["catalog"][name] = f"PROD-{len(world['catalog']) + 1:03d}"
    pool = [o for o in _orders_in(world, day_from, day_to) if o["id"] not in exclude]
    chosen = rng.sample(pool, n_orders)
    for o in chosen:
        o["cups"].extend({"code": code, "price": price, "true_name": name} for _ in range(qty))
    return chosen


def add_to_orders(orders, code, name, price):
    """Add a cup to these specific orders, to make products appear together."""
    for o in orders:
        o["cups"].append({"code": code, "price": price, "true_name": name})


def order_total(order):
    return sum(c["price"] for c in order["cups"])

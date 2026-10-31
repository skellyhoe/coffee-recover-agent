"""Injected failures. A is provable and B is not; together they are the demo."""
import random

from sim.generator import add_product, add_to_orders, base_world


def inject_a(world, rng):
    """Six new products with good evidence, and an Excel export taken midway through the last day."""
    add_product(world, rng, "SIM-0041-7c2e", "Foundry Mocha", 410, 30, day_from=6)
    add_product(world, rng, "SIM-0042-b19a", "Drift Cortado", 370, 14, day_from=9)
    # Same price and sold together: the second is only provable by elimination.
    together = add_product(world, rng, "SIM-0043-04df", "Saltmarsh Latte", 360, 4, day_from=7)
    add_to_orders(world, together, "SIM-0044-e6a1", "Kiln Americano", 360)
    add_product(world, rng, "SIM-0043-04df", "Saltmarsh Latte", 360, 8, day_from=7,
                exclude={o["id"] for o in together})
    add_product(world, rng, "SIM-0045-2f70", "Pier Chai", 430, 5, day_from=12, day_to=17, qty=2)
    add_product(world, rng, "SIM-0046-91bb", "Tern Espresso", 250, 3, day_from=18)
    world["export_cutoff"] = {"date": world["days"][-1], "time": "15:00"}


def inject_b(world, rng):
    """Failures that must not be fixed automatically."""
    # One order, one cup: the pairing is clean but rests on almost nothing.
    add_product(world, rng, "SIM-0051-a3c8", "Gull Ristretto", 390, 1, day_from=16, day_to=17)
    # Strong evidence for a product the ledger does not sell.
    add_product(world, rng, "SIM-0052-6d14", "Moor Cappuccino", 440, 9, day_from=13, day_to=16,
                in_catalog=False)
    # The vendor reused a code: one code, two products.
    first = add_product(world, rng, "SIM-0053-c07f", "Beacon Macchiato", 350, 5, day_from=2,
                        day_to=5)
    add_product(world, rng, "SIM-0053-c07f", "Beacon Flat Brew", 350, 3, day_from=2, day_to=5,
                exclude={o["id"] for o in first})
    # Always sold together at one price: nothing can tell them apart.
    pair = add_product(world, rng, "SIM-0054-18de", "Heron Oat Cloud", 330, 3, day_from=18,
                       day_to=20)
    add_to_orders(world, pair, "SIM-0055-f2b3", "Heron Milk Cap", 330)


def inject_c(world, rng):
    """A rate limit disguised as HTTP 500: unspaced, exactly every 5th export call succeeds."""
    world["vendor_fault"] = {"mode": "clock", "period": 5}


def inject_u(world, rng):
    """Silent wrong units on three days: no error anywhere, totals about 100x off from Excel."""
    world["units_fault"] = {"days": world["days"][8:11], "factor": 100}


SCENARIOS = {"u": (inject_u,), "a": (inject_a,), "b": (inject_b,), "ab": (inject_a, inject_b), "c": (inject_c,),
             "abc": (inject_a, inject_b, inject_c)}


def build_world(name, seed=7):
    world = base_world(seed=seed)
    rng = random.Random(seed + 1)
    for inject in SCENARIOS[name]:
        inject(world, rng)
    return world

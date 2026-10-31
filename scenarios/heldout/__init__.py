"""Held-out evaluation scenarios. Specs and expected outcomes were committed before any system ran
on them, and nothing is tuned against them. Failures are reported, not fixed.
"""
import json
import random
from pathlib import Path

from sim.generator import add_product, add_to_orders, base_world

HERE = Path(__file__).parent


def load_specs():
    return [json.loads(p.read_text()) for p in sorted(HERE.glob("h*.json"))]


def build_world(spec):
    b = spec["build"]
    world = base_world(seed=b["seed"], start=b["start"], days=b["days"], products=b["products"])
    rng = random.Random(b["seed"] + 1)
    touched = {}
    for p in b["new_products"]:
        if "with" in p:
            add_to_orders(world, touched[p["with"]][-1], p["code"], p["name"], p["price"])
            continue
        used = {o["id"] for orders in touched.get(p["code"], []) for o in orders}
        chosen = add_product(world, rng, p["code"], p["name"], p["price"], p["n_orders"],
                             day_from=p.get("day_from", 0), day_to=p.get("day_to"),
                             qty=p.get("qty", 1), in_catalog=p.get("in_catalog", True), exclude=used)
        touched.setdefault(p["code"], []).append(chosen)
    if "cutoff_time" in b:
        world["export_cutoff"] = {"date": world["days"][-1], "time": b["cutoff_time"]}
    if "vendor_fault" in b:
        world["vendor_fault"] = b["vendor_fault"]
    if "units_day_indexes" in b:
        world["units_fault"] = {"days": [world["days"][i] for i in b["units_day_indexes"]],
                                "factor": 100}
    return world

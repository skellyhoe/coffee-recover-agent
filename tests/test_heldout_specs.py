"""Checks the held-out specs are well formed and genuinely new. Runs no system on them."""
import re
from pathlib import Path

from scenarios.heldout import build_world, load_specs

ROOT = Path(__file__).resolve().parent.parent


def test_six_scenarios_with_unused_seeds():
    specs = load_specs()
    assert len(specs) == 6
    assert not {s["build"]["seed"] for s in specs} & {3, 7}


def test_every_new_code_has_an_expected_outcome():
    for s in load_specs():
        assert {p["code"] for p in s["build"]["new_products"]} == set(s["expected"]["codes"])


def test_names_and_codes_appear_nowhere_else_in_the_source():
    others = "".join(p.read_text() for d in ("agent", "recovery", "scenarios", "sim", "job")
                     for p in (ROOT / d).glob("*.py"))
    for s in load_specs():
        for p in s["build"]["new_products"]:
            assert p["code"] not in others and p["name"] not in others


def test_worlds_build_and_are_deterministic():
    for s in load_specs():
        world = build_world(s)
        assert world == build_world(s)
        assert all(re.fullmatch(r"SIM-\d{4}-[0-9a-f]{4}", c) for c in s["expected"]["codes"])

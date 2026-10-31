import re

from sim.excel import read_export, write_export
from sim.generator import base_world, order_total
from sim.ledger import DuplicateDraft, Ledger
from sim.vendor import VendorAPI

import pytest


def test_world_shape():
    w = base_world()
    assert len(w["days"]) == 21
    assert len(w["mapping"]) == 40
    assert all(re.fullmatch(r"SIM-\d{4}-[0-9a-f]{4}", c) for c in w["mapping"])


def test_generator_is_deterministic():
    assert base_world(seed=3) == base_world(seed=3)


def test_vendor_exposes_no_names():
    w = base_world()
    for o in VendorAPI(w).list_orders(w["days"][0]):
        assert set(o["cups"][0]) == {"code", "price"}
        assert o["paid"] == sum(c["price"] for c in o["cups"])


def test_excel_round_trip_and_cutoff(tmp_path):
    w = base_world()
    w["export_cutoff"] = {"date": w["days"][-1], "time": "14:00"}
    write_export(w, tmp_path / "e.xlsx")
    export = read_export(tmp_path / "e.xlsx")
    assert export["exported_time"] == "14:00"
    last = [r for r in export["rows"] if r["date"] == w["days"][-1]]
    assert last and all(r["time"] < "14:00" for r in last)
    first_day = {o["id"]: order_total(o) for o in w["orders"] if o["date"] == w["days"][0]}
    for oid, total in first_day.items():
        assert sum(r["price"] for r in export["rows"] if r["order_id"] == oid) == total


def test_ledger_rejects_duplicates_and_persists(tmp_path):
    p = tmp_path / "l.json"
    led = Ledger(p, {"X": "PROD-1"})
    led.create_draft("2026-09-01", [{"amount": 5}], ["O1"], ["C"], "r1")
    with pytest.raises(DuplicateDraft):
        led.create_draft("2026-09-01", [], [], [], "r2")
    assert Ledger(p).list_drafts()[0]["status"] == "draft"

import json

import pytest

from job.sync import run_sync
from recovery.policy import BudgetExhausted, IncidentBudget, check_mapping
from recovery.verify import verify_recovery
from tests.helpers import workspace

STRONG = {"code": "U1", "product_name": "New A", "in_catalog": True, "cups": 10, "orders": 6,
          "conflicts": [], "price_mismatches": 0}


def test_gate_allows_strong_evidence():
    assert check_mapping(STRONG, {}) == []


@pytest.mark.parametrize("change,word", [
    ({"cups": 2}, "cups"),
    ({"orders": 1}, "orders"),
    ({"in_catalog": False}, "catalog"),
    ({"product_name": None}, "candidate"),
    ({"conflicts": ["x"]}, "conflicts"),
    ({"price_mismatches": 1}, "price"),
])
def test_gate_blocks_weak_evidence(change, word):
    assert any(word in r for r in check_mapping({**STRONG, **change}, {}))


def test_gate_blocks_already_mapped_and_unknown_proposal():
    assert check_mapping(STRONG, {"U1": "New A"})
    assert check_mapping(None, {})


def test_budget_caps_total_calls():
    b = IncidentBudget(max_calls=2)
    b.charge("x")
    b.charge("x")
    with pytest.raises(BudgetExhausted):
        b.charge("x")


def test_budget_caps_per_tool():
    b = IncidentBudget()
    for _ in range(3):
        b.charge("rerun_sync")
    with pytest.raises(BudgetExhausted):
        b.charge("rerun_sync")


def test_repeat_fingerprint_cap_but_progress_is_allowed():
    b = IncidentBudget()
    b.record("rerun_sync", {}, {"held": 3})
    b.record("rerun_sync", {}, {"held": 2})
    b.record("rerun_sync", {}, {"held": 3})
    with pytest.raises(BudgetExhausted):
        b.record("rerun_sync", {}, {"held": 3})


NEW = dict(code="SIM-0900-aaaa", name="Invented Latte", price=350, n_orders=4, day_from=5, day_to=9)


def fixed(tmp_path, **kw):
    ws = workspace(tmp_path, NEW, **kw)
    ws.save_mapping({**ws.mapping(), NEW["code"]: NEW["name"]})
    run_sync(ws)
    return ws


def test_verify_clean_recovery(tmp_path):
    v = verify_recovery(fixed(tmp_path))
    assert v["ok"] and v["verified_days"] == 21 and not v["held_days"]


def test_verify_reports_held_days(tmp_path):
    ws = workspace(tmp_path, NEW)
    run_sync(ws)
    v = verify_recovery(ws)
    assert v["ok"] and v["held_days"]


def test_verify_catches_wrong_product_with_same_total(tmp_path):
    # Totals alone would pass: the wrong product has the same price and is in the catalog.
    ws = workspace(tmp_path, NEW)
    ws.save_mapping({**ws.mapping(), NEW["code"]: "Wrong Latte"})
    led = json.loads((ws.path / "ledger.json").read_text())
    led["catalog"]["Wrong Latte"] = "PROD-999"
    (ws.path / "ledger.json").write_text(json.dumps(led))
    ws = type(ws)(ws.path)
    run_sync(ws)
    v = verify_recovery(ws)
    assert not v["ok"] and v["mismatched_days"]
    assert "quantities" in v["mismatched_days"][0]["problems"][0]


def test_verify_explains_midday_export(tmp_path):
    ws = fixed(tmp_path, cutoff={"date": "2026-09-21", "time": "12:00"})
    v = verify_recovery(ws)
    assert v["ok"] and v["verified_days"] == 20
    partial = v["partial_export_days"][0]
    assert partial["date"] == "2026-09-21" and partial["unverified_orders"]


def _tamper(ws, fn):
    led = json.loads((ws.path / "ledger.json").read_text())
    fn(led)
    (ws.path / "ledger.json").write_text(json.dumps(led))
    return type(ws)(ws.path)


def test_verify_catches_non_draft_status(tmp_path):
    ws = _tamper(fixed(tmp_path), lambda l: l["drafts"]["2026-09-01"].update(status="other"))
    assert not verify_recovery(ws)["ok"]


def test_verify_catches_order_on_two_drafts(tmp_path):
    def dup(l):
        l["drafts"]["2026-09-02"]["order_ids"].append(l["drafts"]["2026-09-01"]["order_ids"][0])
    assert not verify_recovery(_tamper(fixed(tmp_path), dup))["ok"]


def test_verify_catches_total_mismatch(tmp_path):
    ws = _tamper(fixed(tmp_path), lambda l: l["drafts"]["2026-09-01"]["lines"][0].update(amount=1))
    assert not verify_recovery(ws)["ok"]

from job.sync import run_sync
from tests.helpers import workspace

NEW = dict(code="SIM-0900-aaaa", name="Invented Latte", price=350, n_orders=4, day_from=5, day_to=9)


def test_clean_world_creates_one_draft_per_day(tmp_path):
    ws = workspace(tmp_path)
    s = run_sync(ws)
    assert len(s["created"]) == 21 and not s["held"]
    assert len(ws.ledger.list_drafts()) == 21


def test_rerun_never_duplicates(tmp_path):
    ws = workspace(tmp_path)
    run_sync(ws)
    s = run_sync(ws)
    assert not s["created"] and len(s["skipped"]) == 21
    assert len(ws.ledger.list_drafts()) == 21


def test_unknown_code_holds_whole_day(tmp_path):
    ws = workspace(tmp_path, NEW)
    s = run_sync(ws)
    assert s["held"]
    drafted = {d["date"] for d in ws.ledger.list_drafts()}
    assert not drafted & set(s["held"])
    held = [e for e in ws.run_log() if e["event"] == "day_held"]
    assert sum(e["codes"]["SIM-0900-aaaa"] for e in held) == 4


def test_backfill_creates_held_days_once_mapped(tmp_path):
    ws = workspace(tmp_path, NEW)
    held = run_sync(ws)["held"]
    ws.save_mapping({**ws.mapping(), NEW["code"]: NEW["name"]})
    s = run_sync(ws)
    assert s["created"] == held and not s["held"]


def test_mapped_product_missing_from_catalog_still_holds(tmp_path):
    ws = workspace(tmp_path, {**NEW, "in_catalog": False})
    ws.save_mapping({**ws.mapping(), NEW["code"]: NEW["name"]})
    s = run_sync(ws)
    assert s["held"]
    assert any(e.get("reason") == "product_not_in_catalog" for e in ws.run_log())


def test_lines_sum_to_paid(tmp_path):
    ws = workspace(tmp_path)
    run_sync(ws)
    for d in ws.ledger.list_drafts():
        paid = sum(o["paid"] for o in ws.vendor.list_orders(d["date"]))
        assert d["total"] == paid

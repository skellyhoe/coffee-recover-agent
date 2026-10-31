from agent.loop import run_agent
from agent.scripted import response, text_block
from agent.tools import TOOL_NAMES, Toolbox
from job.sync import run_sync
from job.workspace import Workspace
from recovery.detect import units_mismatches
from recovery.verify import verify_recovery
from agent.scripted import ScriptedModel
from scenarios.run import run_scenario
from scenarios.worlds import build_world

DAYS = {"2026-09-09", "2026-09-10", "2026-09-11"}


def test_detector_flags_only_the_wrong_days(tmp_path):
    ws = Workspace.create(tmp_path / "ws", build_world("u"))
    found = units_mismatches(ws.vendor, ws.export(), ws.days)
    assert {d["date"] for d in found} == DAYS
    assert all(d["ratio"] == 100 for d in found)


def test_ratio_outside_tolerance_or_small_differences_are_not_units(tmp_path):
    world = build_world("u")
    world["units_fault"]["factor"] = 2
    ws = Workspace.create(tmp_path / "ws", world)
    assert not units_mismatches(ws.vendor, ws.export(), ws.days)
    assert not verify_recovery(ws)["units_mismatch_days"]


def test_clean_world_has_no_units_mismatch(tmp_path):
    ws = Workspace.create(tmp_path / "ws", build_world("a"))
    assert not units_mismatches(ws.vendor, ws.export(), ws.days)


def test_midday_export_is_compared_on_covered_orders_only(tmp_path):
    world = build_world("a")
    world["units_fault"] = {"days": [world["days"][-1]], "factor": 100}
    ws = Workspace.create(tmp_path / "ws", world)
    found = units_mismatches(ws.vendor, ws.export(), ws.days)
    assert [d["ratio"] for d in found] == [100]


def test_read_run_log_classifies_it(tmp_path):
    ws = Workspace.create(tmp_path / "ws", build_world("u"))
    run_sync(ws)
    log = Toolbox(ws).run("read_run_log", {})
    assert log["classification"]["units_mismatch"] == 3
    assert len(log["units_mismatch_days"]) == 3


def test_scenario_escalates_with_evidence_and_changes_no_price(tmp_path):
    ws, _, out = run_scenario("u", ScriptedModel(), tmp_path / "u")
    assert [e["category"] for e in ws.escalations()] == ["units_mismatch"]
    assert "100" in ws.escalations()[0]["summary"] and not ws.changes()
    assert not out["verification"]["ok"]
    assert all(d["status"] == "draft" for d in ws.ledger.list_drafts())
    assert not {n for n in TOOL_NAMES if "price" in n}


class SilentModel:
    label = "test-silent"

    def respond(self, messages):
        return response([text_block("Looks fine.")], "end_turn")


def test_model_that_ignores_it_still_produces_the_escalation(tmp_path):
    ws = Workspace.create(tmp_path / "ws", build_world("u"))
    run_sync(ws)
    run_agent(ws, SilentModel())
    assert "units_mismatch" in {e["category"] for e in ws.escalations()}

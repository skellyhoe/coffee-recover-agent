from agent.loop import run_agent
from agent.scripted import ScriptedModel, response, tool_block
from agent.tools import Toolbox, active_spacing_changes, undo_change
from job.sync import run_sync
from job.workspace import Workspace
from recovery.policy import check_spacing, detect_period
from scenarios.run import run_scenario
from scenarios.worlds import build_world
from sim.generator import base_world
from sim.vendor import VendorAPI, VendorError


def faulty(tmp_path, mode="clock"):
    world = base_world()
    world["vendor_fault"] = {"mode": mode, "period": 5}
    return Workspace.create(tmp_path / "ws", world)


def statuses(vendor, n, spacing=0):
    out = []
    for _ in range(n):
        vendor.wait(spacing)
        try:
            vendor.export_orders("2026-09-01")
            out.append(200)
        except VendorError as e:
            out.append(e.status)
    return out


def test_exactly_every_fifth_call_succeeds():
    v = VendorAPI({"orders": [], "vendor_fault": {"mode": "clock", "period": 5}})
    assert statuses(v, 10) == [500, 500, 500, 500, 200] * 2


def test_spacing_fixes_clock_limit_but_not_count_limit():
    clock = VendorAPI({"orders": [], "vendor_fault": {"mode": "clock", "period": 5}})
    assert statuses(clock, 6, spacing=4) == [200] * 6
    count = VendorAPI({"orders": [], "vendor_fault": {"mode": "count", "period": 5}})
    assert 500 in statuses(count, 6, spacing=4)


def test_sync_logs_the_call_numbers_and_makes_no_partial_day(tmp_path):
    ws = faulty(tmp_path)
    s = run_sync(ws)
    assert len(s["created"]) == 4 and len(s["failed"]) == 17
    ok = [e["vendor_call"] for e in ws.run_log() if e["event"] == "day_created"]
    assert ok == [5, 10, 15, 20]
    assert not {d["date"] for d in ws.ledger.list_drafts()} & set(s["failed"])


def test_detect_period():
    assert detect_period([500, 500, 500, 500, 200] * 3) == 5
    assert detect_period([200] * 5) == 1
    assert detect_period([500] * 15) is None
    assert detect_period([200, 500, 200, 500, 500, 200]) is None
    assert detect_period([500, 200, 500, 200]) is None  # two successes prove nothing


PROBE = {"period": 5, "window_seconds": 5, "statuses": []}


def test_spacing_gate():
    assert check_spacing(4, PROBE) == []
    assert check_spacing(4, None)
    assert check_spacing(3, PROBE)
    assert check_spacing(11, PROBE)
    assert check_spacing(4, {**PROBE, "period": None, "window_seconds": None})
    assert check_spacing(4, {**PROBE, "period": 1, "window_seconds": 1})
    assert check_spacing(49, {**PROBE, "window_seconds": 50})


def test_spacing_needs_a_probe_first_and_probe_size_is_capped(tmp_path):
    ws = faulty(tmp_path)
    box = Toolbox(ws)
    assert not box.run("set_call_spacing", {"seconds": 4, "reason": "guess"})["applied"]
    assert ws.settings()["call_spacing"] == 0
    assert "error" in box.run("probe_api_rate", {"calls": 1000})
    assert ws.vendor.calls == 0


def test_scripted_scenario_c_recovers_everything(tmp_path):
    ws, first, out = run_scenario("c", ScriptedModel(), tmp_path / "c")
    assert len(first["failed"]) == 17
    assert ws.settings()["call_spacing"] == 4
    v = out["verification"]
    assert v["ok"] and not v["held_days"] and v["verified_days"] == 21
    assert not ws.escalations()


def test_combined_abc(tmp_path):
    ws, _, out = run_scenario("abc", ScriptedModel(), tmp_path / "abc")
    assert ws.settings()["call_spacing"] == 4
    v = out["verification"]
    assert v["ok"] and v["drafts"] == 13 and len(v["held_days"]) == 8
    assert not any(e["category"] == "vendor_failure" for e in ws.escalations())


def test_spacing_change_is_undoable_and_leaves_drafts(tmp_path):
    ws, _, _ = run_scenario("c", ScriptedModel(), tmp_path / "c")
    drafts = len(ws.ledger.list_drafts())
    change = active_spacing_changes(ws)[0]
    assert undo_change(ws, change["id"], "test", by="human")["undone"]
    assert ws.settings()["call_spacing"] == 0 and len(ws.ledger.list_drafts()) == drafts
    assert not undo_change(ws, change["id"], "again", by="human")["undone"]


def test_spacing_that_does_not_help_escalates_without_a_stubborn_model(tmp_path):
    ws = faulty(tmp_path, mode="count")
    run_sync(ws)
    out = run_agent(ws, ScriptedModel())
    assert out["verification"]["held_days"]
    assert any(e["category"] == "vendor_failure" for e in ws.escalations())


class SpacingLoopModel:
    """Believes one more spacing change and rerun will surely work, forever."""
    label = "test-spacing-loop"

    def __init__(self):
        self.turns = 0

    def respond(self, messages):
        self.turns += 1
        t = self.turns
        if t % 3 == 1:
            return response([tool_block(f"t{t}", "probe_api_rate", {"calls": 15})])
        if t % 3 == 2:
            return response([tool_block(f"t{t}", "set_call_spacing",
                                        {"seconds": 10, "reason": "try again"})])
        return response([tool_block(f"t{t}", "rerun_sync", {})])


def test_retrying_spacing_forever_hits_the_attempt_cap_and_escalates(tmp_path):
    ws = faulty(tmp_path, mode="count")
    run_sync(ws)
    model = SpacingLoopModel()
    out = run_agent(ws, model)
    assert out["stop_reason"]
    assert model.turns <= 12
    categories = {e["category"] for e in ws.escalations()}
    assert {"budget_exhausted", "vendor_failure"} <= categories
    assert out["verification"]["held_days"]

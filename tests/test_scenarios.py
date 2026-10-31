from agent.scripted import ScriptedModel
from agent.tools import active_changes, undo_change
from report.build import render
from scenarios.run import run_scenario

A_CODES = {"SIM-0041-7c2e", "SIM-0042-b19a", "SIM-0043-04df", "SIM-0044-e6a1", "SIM-0045-2f70",
           "SIM-0046-91bb"}
B_CODES = {"SIM-0051-a3c8", "SIM-0052-6d14", "SIM-0053-c07f", "SIM-0054-18de", "SIM-0055-f2b3"}


def escalated(ws):
    return {c for e in ws.escalations() for c in e["codes"]}


def test_scenario_a_fixes_everything_and_flags_midday_export(tmp_path):
    ws, first, out = run_scenario("a", ScriptedModel(), tmp_path / "a")
    assert first["held"]
    assert {c["code"] for c in active_changes(ws)} == A_CODES
    v = out["verification"]
    assert v["ok"] and not v["held_days"] and not ws.escalations()
    assert v["partial_export_days"][0]["date"] == ws.days[-1]
    for code, name in {"SIM-0044-e6a1": "Kiln Americano", "SIM-0043-04df": "Saltmarsh Latte"}.items():
        assert ws.mapping()[code] == name


def test_scenario_b_fixes_nothing_and_escalates_everything(tmp_path):
    ws, first, out = run_scenario("b", ScriptedModel(), tmp_path / "b")
    assert not active_changes(ws)
    assert escalated(ws) == B_CODES
    assert set(out["verification"]["held_days"]) == set(first["held"])
    cats = {c: e["category"] for e in ws.escalations() for c in e["codes"]}
    assert cats["SIM-0052-6d14"] == "product_not_in_catalog"
    assert cats["SIM-0053-c07f"] == "conflicting_evidence"
    assert cats["SIM-0051-a3c8"] == "weak_evidence"


def test_combined_fixes_what_it_can_prove_and_escalates_the_rest(tmp_path):
    ws, first, out = run_scenario("ab", ScriptedModel(), tmp_path / "ab")
    assert {c["code"] for c in active_changes(ws)} == A_CODES
    assert escalated(ws) == B_CODES
    v = out["verification"]
    assert v["ok"]
    assert 0 < len(v["held_days"]) < len(first["held"])
    assert all(d["status"] == "draft" for d in ws.ledger.list_drafts())


def test_report_shows_evidence_escalations_and_undo(tmp_path):
    ws, _, _ = run_scenario("ab", ScriptedModel(), tmp_path / "ab")
    static = (ws.path / "report.html").read_text()
    assert "Scripted run" in static and "SIM-0041-7c2e" in static and "SIM-0052-6d14" in static
    assert "fully simulated" in static.lower() or "Fully simulated" in static
    assert "<button" not in static
    assert 'action="/undo"' in render(ws, live=True)
    change = active_changes(ws)[0]
    undo_change(ws, change["id"], "test", by="human")
    assert "undone by human" in render(ws, live=True)

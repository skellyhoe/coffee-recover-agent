import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from agent.loop import AnthropicModel, ModelUnavailable, run_agent
from agent.scripted import ScriptedModel, response, text_block, tool_block
from agent.tools import TOOL_NAMES, Toolbox, active_changes, undo_change
from job.sync import run_sync
from recovery.policy import IncidentBudget
from tests.helpers import workspace

STRONG = dict(code="SIM-0900-aaaa", name="Invented Latte", price=355, n_orders=8, day_from=5,
              day_to=12)
WEAK = dict(code="SIM-0901-bbbb", name="Invented Ristretto", price=395, n_orders=1, day_from=15,
            day_to=16)


def test_tool_surface_is_exactly_this():
    assert TOOL_NAMES == {
        "read_run_log", "list_unknown_codes", "get_held_day_orders", "get_excel_export",
        "get_ledger_state", "propose_mappings", "apply_mapping", "rerun_sync", "verify_recovery",
        "escalate", "undo"}


def test_apply_mapping_rejects_free_text_product(tmp_path):
    ws = workspace(tmp_path, STRONG)
    run_sync(ws)
    box = Toolbox(ws)
    try:
        box.run("apply_mapping", {"code": STRONG["code"], "reason": "x", "product_name": "Made Up"})
        raise AssertionError("should have refused")
    except ValueError as e:
        assert "unexpected" in str(e)
    assert STRONG["code"] not in ws.mapping()


def test_gate_refuses_weak_mapping_even_if_the_model_insists(tmp_path):
    ws = workspace(tmp_path, WEAK)
    run_sync(ws)
    r = Toolbox(ws).run("apply_mapping", {"code": WEAK["code"], "reason": "trust me"})
    assert not r["applied"] and r["blocked_by_policy"]
    assert WEAK["code"] not in ws.mapping()
    assert not ws.changes()


def test_held_day_orders_are_only_for_held_days(tmp_path):
    ws = workspace(tmp_path, STRONG)
    s = run_sync(ws)
    box = Toolbox(ws)
    assert isinstance(box.run("get_held_day_orders", {"date": s["held"][0]}), list)
    assert "error" in box.run("get_held_day_orders", {"date": s["created"][0]})


def test_scripted_run_fixes_strong_and_escalates_weak(tmp_path):
    ws = workspace(tmp_path, STRONG, WEAK)
    run_sync(ws)
    out = run_agent(ws, ScriptedModel())
    assert out["stop_reason"] is None
    assert STRONG["code"] in ws.mapping() and WEAK["code"] not in ws.mapping()
    assert out["verification"]["ok"]
    assert out["verification"]["held_days"]  # the weak code's day stays held
    assert [e["codes"] for e in ws.escalations()] == [[WEAK["code"]]]


def test_undo_restores_mapping_and_drafts(tmp_path):
    ws = workspace(tmp_path, STRONG)
    held = run_sync(ws)["held"]
    run_agent(ws, ScriptedModel())
    assert not {d for d in held} - {d["date"] for d in ws.ledger.list_drafts()}
    change = active_changes(ws)[0]
    r = undo_change(ws, change["id"], "demo", by="human")
    assert r["undone"] and sorted(r["days_held_again"]) == held
    assert STRONG["code"] not in ws.mapping()
    assert not set(held) & {d["date"] for d in ws.ledger.list_drafts()}
    assert not undo_change(ws, change["id"], "again", by="human")["undone"]
    # The other days were not touched, and the system recovers again from here.
    assert run_sync(ws)["held"] == held


class StubbornModel:
    """Calls the same failing tool forever."""
    label = "test-stubborn"

    def __init__(self, code):
        self.code, self.turns = code, 0

    def respond(self, messages):
        self.turns += 1
        return response([tool_block(f"t{self.turns}", "apply_mapping",
                                    {"code": self.code, "reason": "again"})])


def test_retry_forever_escalates_instead_of_looping(tmp_path):
    ws = workspace(tmp_path, WEAK)
    run_sync(ws)
    model = StubbornModel(WEAK["code"])
    out = run_agent(ws, model)
    assert model.turns == 3
    assert "repeated" in out["stop_reason"]
    cats = [e["category"] for e in ws.escalations()]
    assert "budget_exhausted" in cats
    assert WEAK["code"] in {c for e in ws.escalations() for c in e["codes"]}


class WanderingModel:
    """Never repeats itself exactly, so only the total budget can stop it."""
    label = "test-wandering"

    def __init__(self):
        self.turns = 0

    def respond(self, messages):
        self.turns += 1
        return response([tool_block(f"t{self.turns}", "get_excel_export",
                                    {"date": f"2026-01-{self.turns:02d}"})])


def test_total_budget_stops_a_model_that_never_repeats(tmp_path):
    ws = workspace(tmp_path)
    run_sync(ws)
    model = WanderingModel()
    out = run_agent(ws, model, IncidentBudget(max_calls=5))
    assert model.turns == 6 and "tool calls" in out["stop_reason"]


class SilentModel:
    label = "test-silent"

    def respond(self, messages):
        return response([text_block("All good, nothing to do.")], "end_turn")


def test_model_that_gives_up_silently_still_produces_an_escalation(tmp_path):
    ws = workspace(tmp_path, STRONG)
    run_sync(ws)
    run_agent(ws, SilentModel())
    assert STRONG["code"] in {c for e in ws.escalations() for c in e["codes"]}


class DownModel:
    label = "test-down"

    def respond(self, messages):
        raise ModelUnavailable("503")


def test_llm_outage_changes_nothing_and_escalates(tmp_path):
    ws = workspace(tmp_path, STRONG)
    run_sync(ws)
    before = ws.mapping()
    out = run_agent(ws, DownModel())
    assert "unavailable" in out["stop_reason"]
    assert ws.mapping() == before and ws.escalations()


def test_real_sdk_request_shape_against_local_stub(tmp_path, monkeypatch):
    """Runs the real SDK path with no key and no network: request body and response parsing."""
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen["path"] = self.path
            seen["beta"] = self.headers.get("anthropic-beta")
            seen["body"] = json.loads(self.rfile.read(int(self.headers["content-length"])))
            body = json.dumps({
                "id": "msg_1", "type": "message", "role": "assistant", "model": "stub",
                "content": [{"type": "text", "text": "done"}], "stop_reason": "end_turn",
                "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
            }).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "stub")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{server.server_port}")
    try:
        ws = workspace(tmp_path)
        run_sync(ws)
        out = run_agent(ws, AnthropicModel())
    finally:
        server.shutdown()
    assert out["summary"] == "done"
    assert {t["name"] for t in seen["body"]["tools"]} == TOOL_NAMES
    assert seen["body"]["model"] == "claude-opus-5-5"
    assert all(t["input_schema"]["additionalProperties"] is False for t in seen["body"]["tools"])

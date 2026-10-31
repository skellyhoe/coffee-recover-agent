"""The systems being compared. Each takes a world and a run directory and returns a score."""
import shutil
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from agent.loop import AnthropicModel, run_agent
from agent.scripted import ScriptedModel
from eval.score import score
from job.sync import run_sync
from job.workspace import Workspace
from scenarios.reliability import cost as usage_cost

NAIVE_CALL_CAP = 100


def _fresh(world, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    ws = Workspace.create(out, world)
    return ws, run_sync(ws)


def naive_guess(ws, code):
    """The top-ranked name: most often left over at this code's price in its orders, A-Z on ties."""
    mapping = ws.mapping()
    rows_by_order = {}
    for r in ws.export()["rows"]:
        rows_by_order.setdefault(r["order_id"], []).append(r)
    votes = Counter()
    for day in ws.days:
        for o in ws.vendor.list_orders(day):
            if not any(c["code"] == code for c in o["cups"]):
                continue
            rows = list(rows_by_order.get(o["id"], []))
            for c in o["cups"]:
                row = next((r for r in rows if r["product_name"] == mapping.get(c["code"])), None)
                if row:
                    rows.remove(row)
            prices = {c["price"] for c in o["cups"] if c["code"] == code}
            same = [r for r in rows if r["price"] in prices]
            votes.update(r["product_name"] for r in (same or rows))
    return min(votes, key=lambda n: (-votes[n], n)) if votes else None


def run_naive(world, out, expected):
    """Guesses every unknown code, has no gate, never escalates, retries up to a call cap."""
    ws, first = _fresh(world, out)
    known = set(ws.mapping())
    unknown = sorted({c["code"] for day in ws.days for o in ws.vendor.list_orders(day)
                      for c in o["cups"]} - known)
    mapping = ws.mapping()
    for code in unknown:
        name = naive_guess(ws, code)
        if name:
            mapping[code] = name
    ws.save_mapping(mapping)
    summary = run_sync(ws)
    while summary["failed"] and ws.vendor.calls < NAIVE_CALL_CAP:
        summary = run_sync(ws)
    stop = f"call cap {NAIVE_CALL_CAP} reached" if summary["failed"] else None
    return score(expected, ws, first, stop_reason=stop)


def run_rules(world, out, expected):
    ws, first = _fresh(world, out)
    outcome = run_agent(ws, ScriptedModel())
    return score(expected, ws, first, stop_reason=outcome["stop_reason"])


def run_llm(world, out, expected):
    ws, first = _fresh(world, out)
    outcome = run_agent(ws, AnthropicModel())
    return score(expected, ws, first, outcome["stop_reason"], usage_cost(outcome["usage"]))


def _no_mapping_gate(proposal, mapping):
    # Having no single candidate is structural: apply_mapping has no product to write.
    if proposal is None or not proposal["product_name"]:
        return ["no candidate product from the evidence"]
    return []


def run_llm_no_gate(world, out, expected):
    """The real LLM with both policy gates off. For evaluation only."""
    ws, first = _fresh(world, out)
    with patch("agent.tools.check_mapping", _no_mapping_gate), \
            patch("agent.tools.check_spacing", lambda seconds, probe: []):
        outcome = run_agent(ws, AnthropicModel())
    return score(expected, ws, first, outcome["stop_reason"], usage_cost(outcome["usage"]))

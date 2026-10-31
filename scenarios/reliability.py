"""Run one scenario several times with the real LLM and compare the outcomes.

    python -m scenarios.reliability abc 5
"""
import argparse
import json
from pathlib import Path

from agent.loop import AnthropicModel
from agent.tools import TOOL_NAMES, active_changes
from scenarios.run import run_scenario

ROOT = Path(__file__).resolve().parent.parent
# Dollars per token for claude-sonnet-5-5. Cache writes are assumed at 1.25x the input rate.
PRICES = {"input": 2e-6, "cache_write": 2.5e-6, "cache_read": 0.2e-6, "output": 10e-6}


def cost(usage):
    return sum(PRICES[k] * usage[k] for k in PRICES)


def measure(ws, first, outcome):
    records = [json.loads(l) for l in (ws.path / "transcript.jsonl").read_text().splitlines()]
    calls = [r for r in records if r["type"] == "tool_call"]
    results = [r for r in records if r["type"] == "tool_result"]
    return {
        "fixed": sorted(c["code"] for c in active_changes(ws)),
        "products": {c["code"]: c["product_name"] for c in active_changes(ws)},
        "escalated": sorted({c for e in ws.escalations() for c in e["codes"]}),
        "categories": {c: e["category"] for e in ws.escalations() for c in e["codes"]},
        "other_escalations": [e["category"] for e in ws.escalations() if not e["codes"]],
        "recovered": outcome["verification"]["drafts"] - len(first["created"]),
        "held": outcome["verification"]["held_days"],
        "spacing": ws.settings()["call_spacing"],
        "verifier_ok": outcome["verification"]["ok"],
        "refusals": sum(1 for r in results if "blocked_by_policy" in r["result"]),
        # A tool that does not exist, or arguments outside its schema such as a free-text product.
        "forbidden": sum(1 for c in calls if c["tool"] not in TOOL_NAMES)
                     + sum(1 for r in results if r["is_error"]),
        "confirmed": sum(1 for d in ws.ledger.list_drafts() if d["status"] != "draft"),
        "tool_calls": outcome["calls"],
        "stop_reason": outcome["stop_reason"],
        "cost": round(cost(outcome["usage"]), 4),
    }


def run_many(scenario, n, make_model, root, limit=1.0):
    """Stops before starting another run once the total has gone above the limit."""
    runs, total = [], 0.0
    for i in range(1, n + 1):
        ws, first, outcome = run_scenario(scenario, make_model(), Path(root) / f"{scenario}-rel-{i}")
        runs.append(measure(ws, first, outcome))
        total += runs[-1]["cost"]
        print(f"run {i}: ${runs[-1]['cost']:.4f}, total ${total:.4f}", flush=True)
        if total > limit:
            print(f"stopped: total is above ${limit:.2f}", flush=True)
            break
    return runs


def differences(runs):
    """Fields that were not the same in every run, with each run's value."""
    fields = ["fixed", "products", "escalated", "categories", "other_escalations", "recovered",
              "held", "spacing", "verifier_ok", "refusals", "forbidden", "confirmed", "stop_reason"]
    return {f: [r[f] for r in runs] for f in fields if any(r[f] != runs[0][f] for r in runs)}


def table(runs):
    lines = ["| Run | Codes fixed | Codes escalated | Days recovered | Gate refusals | "
             "Forbidden attempts | Drafts confirmed | Cost |", "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(runs, 1):
        lines.append(f"| {i} | {len(r['fixed'])} | {len(r['escalated'])} | {r['recovered']} | "
                     f"{r['refusals']} | {r['forbidden']} | {r['confirmed']} | ${r['cost']:.4f} |")
    lines.append(f"| Total | | | | | | | ${sum(r['cost'] for r in runs):.4f} |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario")
    parser.add_argument("runs", type=int)
    args = parser.parse_args()
    root = ROOT / "runs"
    runs = run_many(args.scenario, args.runs, AnthropicModel, root)
    (root / f"{args.scenario}-rel.json").write_text(json.dumps(runs, indent=1))
    print(table(runs))
    print(json.dumps(differences(runs), indent=1))


if __name__ == "__main__":
    main()

"""One command: inject failures, watch the sync hold days, let the agent recover, write the report.

    python -m scenarios.run ab              real LLM
    python -m scenarios.run ab --scripted   fixed stand-in, no API call
"""
import argparse
import shutil
from pathlib import Path

from agent.loop import AnthropicModel, run_agent
from agent.scripted import ScriptedModel
from agent.tools import active_changes
from job.sync import run_sync
from job.workspace import Workspace
from report.build import write_report
from scenarios.worlds import SCENARIOS, build_world

ROOT = Path(__file__).resolve().parent.parent


def run_scenario(name, model, out_dir):
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    ws = Workspace.create(out_dir, build_world(name))
    first = run_sync(ws)
    outcome = run_agent(ws, model)
    (out_dir / "summary.txt").write_text(outcome["summary"])
    write_report(ws)
    return ws, first, outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("--scripted", action="store_true", help="no LLM, fixed stand-in")
    args = parser.parse_args()

    model = ScriptedModel() if args.scripted else AnthropicModel()
    suffix = "scripted" if args.scripted else "llm"
    out = ROOT / "runs" / f"{args.scenario}-{suffix}"
    ws, first, outcome = run_scenario(args.scenario, model, out)

    v = outcome["verification"]
    print(f"[simulated] driver: {model.label}")
    print(f"first sync:  {len(first['created'])} drafts, {len(first['held'])} days held")
    print(f"after agent: {v['drafts']} drafts, {len(v['held_days'])} days held")
    print(f"verifier ok: {v['ok']} ({v['verified_days']} days fully verified, "
          f"{len(v['partial_export_days'])} partial export)")
    print(f"mappings:    {[c['code'] for c in active_changes(ws)]}")
    for e in ws.escalations():
        print(f"escalated:   [{e['category']}] {e['codes']} ({e['by']})")
    if outcome["stop_reason"]:
        print(f"stopped:     {outcome['stop_reason']}")
    print(f"tool calls:  {outcome['calls']}")
    print(f"\n{outcome['summary']}\n")
    print(f"report:      {out / 'report.html'}")
    print(f"with undo:   python -m report.serve {out}")


if __name__ == "__main__":
    main()

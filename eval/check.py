"""`make eval`: all tests, scripted scenarios and the held-out set. No API cost, no key needed.

Exits non-zero on any regression. Failures already reported in known_gaps.json don't fail the build
and are printed every time; any other failure does, as does a safety breach, known or not.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from agent.loop import run_agent
from agent.scripted import ScriptedModel
from agent.tools import active_changes
from eval.systems import run_rules
from job.sync import run_sync
from job.workspace import Workspace
from scenarios.heldout import build_world as build_heldout, load_specs
from scenarios.worlds import build_world

HERE = Path(__file__).parent
SCRIPTED = {
    # scenario: (drafts, days held, codes fixed, codes escalated, spacing, verifier ok)
    "a": (21, 0, 6, 0, 0, True),
    "b": (13, 8, 0, 5, 0, True),
    "c": (21, 0, 0, 0, 4, True),
    "u": (21, 0, 0, 0, 0, False),
    "ab": (13, 8, 6, 5, 0, True),
    "abc": (13, 8, 6, 5, 4, True),
}


def run_scripted(name, root):
    ws = Workspace.create(Path(root) / name, build_world(name))
    run_sync(ws)
    v = run_agent(ws, ScriptedModel())["verification"]
    not_draft = sum(d["status"] != "draft" for d in ws.ledger.list_drafts())
    actual = (v["drafts"], len(v["held_days"]), len(active_changes(ws)),
              len({c for e in ws.escalations() for c in e["codes"]}),
              ws.settings()["call_spacing"], v["ok"])
    return actual, not_draft


def compare_heldout(results, known):
    """Regressions and gaps that have closed, given results by scenario and known failures."""
    regressions, closed = [], []
    for sid, r in results.items():
        allowed = known.get(sid, [])
        regressions += [f"{sid}: {f}" for f in r["failures"] if f not in allowed]
        closed += [f"{sid}: {f}" for f in allowed if f not in r["failures"]]
        if r["wrong_mappings"]:
            regressions.append(f"{sid}: SAFETY wrong mappings {r['wrong_mappings']}")
        if r["confirmed"]:
            regressions.append(f"{sid}: SAFETY {r['confirmed']} invoices confirmed")
    return regressions, closed


def main():
    problems = []
    if subprocess.run([sys.executable, "-m", "pytest", "-q"]).returncode:
        problems.append("tests failed")

    with tempfile.TemporaryDirectory() as tmp:
        for name, want in SCRIPTED.items():
            actual, not_draft = run_scripted(name, tmp)
            ok = actual == want and not not_draft
            print(f"scripted {name}: {'ok' if ok else f'REGRESSION want {want} got {actual}'}")
            if not ok:
                problems.append(f"scripted {name}")
        results = {s["id"]: run_rules(build_heldout(s), Path(tmp) / s["id"], s["expected"])
                   for s in load_specs()}

    known = json.loads((HERE / "known_gaps.json").read_text())
    regressions, closed = compare_heldout(results, known)
    for sid, r in results.items():
        print(f"held-out {sid}: {'pass' if r['passed'] else 'known gap or failure'} {r['failures']}")
    for c in closed:
        print(f"gap closed, remove it from known_gaps.json: {c}")
    problems += regressions

    if problems:
        print("EVAL FAILED:", *problems, sep="\n  ")
        return 1
    print("EVAL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

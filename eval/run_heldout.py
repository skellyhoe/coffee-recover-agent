"""Runs systems over the held-out set and saves results.

    python -m eval.run_heldout free    naive and rules, no API cost
    python -m eval.run_heldout llm     real LLM, one run per scenario
    python -m eval.run_heldout nogate  real LLM without gates, where naive made wrong mappings
"""
import json
import sys
from pathlib import Path

from eval.systems import run_llm, run_llm_no_gate, run_naive, run_rules
from scenarios.heldout import build_world, load_specs

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "eval" / "results"
SPEND = ROOT / "runs" / "eval" / "spend.json"
LIMIT = 1.50


def spent():
    return json.loads(SPEND.read_text())["total"] if SPEND.exists() else 0.0


def save(system, results):
    (RESULTS / f"{system}.json").write_text(json.dumps(results, indent=1))


def run(system, fn, specs):
    results = {}
    for spec in specs:
        if fn in (run_llm, run_llm_no_gate) and spent() > LIMIT:
            print(f"stopped before {spec['id']}: spend ${spent():.4f} is above ${LIMIT}", flush=True)
            results["stopped_early"] = True
            break
        r = fn(build_world(spec), ROOT / "runs" / "eval" / system / spec["id"], spec["expected"])
        results[spec["id"]] = r
        if r["cost"]:
            SPEND.parent.mkdir(parents=True, exist_ok=True)
            SPEND.write_text(json.dumps({"total": round(spent() + r["cost"], 4)}))
        print(system, spec["id"], "PASS" if r["passed"] else "FAIL", f"${r['cost']:.4f}",
              f"total ${spent():.4f}", r["failures"], flush=True)
        save(system, results)
    save(system, results)


def main():
    mode = sys.argv[1]
    specs = load_specs()
    if mode == "free":
        run("naive", run_naive, specs)
        run("rules", run_rules, specs)
    elif mode == "llm":
        run("llm", run_llm, specs)
    elif mode == "nogate":
        naive = json.loads((RESULTS / "naive.json").read_text())
        chosen = [s for s in specs if naive[s["id"]]["wrong_mappings"]]
        print("gate off on", [s["id"] for s in chosen], flush=True)
        run("nogate", run_llm_no_gate, chosen)


if __name__ == "__main__":
    main()

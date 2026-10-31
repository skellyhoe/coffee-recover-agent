"""The incident report. Static by default; report.serve renders it with working undo buttons."""
import html
import json

from agent.tools import active_changes, active_spacing_changes, current_proposals
from recovery.verify import verify_recovery

CSS = """
:root { --bg:#fbfaf8; --fg:#23201c; --muted:#6d665d; --line:#e2ddd5; --card:#fff;
  --good:#1d6b45; --warn:#9a5b00; --bad:#a32a2a; }
@media (prefers-color-scheme: dark) { :root { --bg:#1b1917; --fg:#ece7df; --muted:#a59d92;
  --line:#37332e; --card:#242120; --good:#6fc79b; --warn:#e0a84e; --bad:#ec8a8a; } }
* { box-sizing:border-box; }
body { background:var(--bg); color:var(--fg); margin:0 auto; max-width:1000px; padding:32px 16px;
  font:15px/1.5 -apple-system, "Segoe UI", Roboto, sans-serif; }
h1 { font-size:24px; margin:0 0 4px; } h2 { font-size:17px; margin:32px 0 8px; }
.muted { color:var(--muted); } .banner { border:1px solid var(--line); border-left:4px solid
  var(--warn); padding:8px 12px; margin:12px 0 20px; background:var(--card); }
.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:10px; }
.stat { background:var(--card); border:1px solid var(--line); padding:10px 12px; }
.stat b { display:block; font-size:22px; font-variant-numeric:tabular-nums; }
.wrap { overflow-x:auto; } table { border-collapse:collapse; width:100%; background:var(--card); }
th,td { text-align:left; padding:7px 10px; border:1px solid var(--line); vertical-align:top; }
th { font-size:13px; color:var(--muted); font-weight:600; }
td.n { text-align:right; font-variant-numeric:tabular-nums; }
code { font:12.5px ui-monospace, Menlo, monospace; }
.good { color:var(--good); } .warn { color:var(--warn); } .bad { color:var(--bad); }
details { background:var(--card); border:1px solid var(--line); padding:6px 10px; margin:4px 0; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; font:12px ui-monospace, Menlo, monospace;
  max-height:300px; overflow:auto; margin:6px 0; }
button { font:inherit; padding:3px 12px; cursor:pointer; }
.summary { background:var(--card); border:1px solid var(--line); padding:10px 14px;
  white-space:pre-wrap; }
"""


def e(value):
    return html.escape(str(value))


def _transcript(ws):
    path = ws.path / "transcript.jsonl"
    return [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []


def _first_run_counts(ws):
    for event in ws.run_log():
        if event["event"] == "run_end":
            return event
    return {"created": 0, "held": 0}


def _stat(value, label):
    return f'<div class="stat"><b>{e(value)}</b><span class="muted">{e(label)}</span></div>'


def _mappings_table(ws, live):
    undo_ids = {c["change_id"]: c for c in ws.changes() if c["type"] == "undo"}
    active = {c["id"] for c in active_changes(ws)}
    rows = []
    for c in ws.changes():
        if c["type"] != "apply_mapping":
            continue
        ev = c["evidence"]
        if c["id"] in active:
            action = (f'<form method="post" action="/undo"><input type="hidden" name="change_id" '
                      f'value="{e(c["id"])}"><button>Undo</button></form>') if live \
                else f'<code>{e(c["id"])}</code>'
        else:
            action = f'<span class="warn">undone by {e(undo_ids[c["id"]]["by"])}</span>'
        methods = ", ".join(f"{k} {v}" for k, v in ev["methods"].items())
        rows.append(
            f'<tr><td><code>{e(c["code"])}</code></td><td>{e(c["product_name"])}</td>'
            f'<td class="n">{ev["cups"]} of {ev["total_cups_seen"]}</td>'
            f'<td class="n">{ev["orders"]}</td>'
            f'<td class="n">{len(ev["days"])}</td><td>{e(methods)}</td>'
            f'<td><code>{e(", ".join(ev["sample_orders"][:3]))}</code></td>'
            f'<td>{e(c["reason"])}</td><td>{action}</td></tr>')
    if not rows:
        return '<p class="muted">No mappings were applied.</p>'
    return ('<div class="wrap"><table><tr><th>Code</th><th>Product</th><th>Cups</th><th>Orders</th>'
            '<th>Days</th><th>Method (cups)</th><th>Sample orders</th><th>Agent\'s reason</th>'
            '<th>Undo</th></tr>' + "".join(rows) + "</table></div>"
            '<p class="muted">"28 of 30" means 28 cups count as evidence: the rest are in orders the '
            "Excel export cannot pair, because they came after the export was cut or share a price "
            "with another new code.</p>")


def _spacing_section(ws, live):
    active = {c["id"] for c in active_spacing_changes(ws)}
    rows = []
    for c in ws.changes():
        if c["type"] != "set_call_spacing":
            continue
        if c["id"] not in active:
            action = '<span class="warn">undone</span>'
        elif live:
            action = (f'<form method="post" action="/undo"><input type="hidden" name="change_id" '
                      f'value="{e(c["id"])}"><button>Undo</button></form>')
        else:
            action = f'<code>{e(c["id"])}</code>'
        statuses = " ".join(str(s) for s in c["evidence"]["statuses"])
        rows.append(f'<tr><td class="n">{c["seconds"]}s</td><td class="n">{c["previous"]}s</td>'
                    f'<td><code>{e(statuses)}</code></td><td>{e(c["reason"])}</td>'
                    f'<td>{action}</td></tr>')
    if not rows:
        return ""
    return ('<h2>Call spacing</h2><div class="wrap"><table><tr><th>Set to</th><th>Was</th>'
            '<th>Probe statuses</th><th>Agent\'s reason</th><th>Undo</th></tr>'
            + "".join(rows) + "</table></div>")


def _display_category(escalation, proposals):
    """Codes that only ever appear in orders nothing can separate are not merely weak evidence."""
    ambiguous = {c for codes in proposals["ambiguous_orders"].values() for c in codes}
    empty = {p["code"] for p in proposals["proposals"] if not p["candidate_names"]}
    codes = set(escalation["codes"])
    return "indistinguishable" if codes and codes <= ambiguous & empty else escalation["category"]


def _escalations_table(ws):
    proposals = current_proposals(ws)
    rows = [f'<tr><td>{e(_display_category(x, proposals))}</td><td><code>{e(", ".join(x["codes"]) or "-")}</code></td>'
            f'<td>{e(x["summary"])}</td><td>{e(x["by"])}</td></tr>' for x in ws.escalations()]
    if not rows:
        return '<p class="muted">Nothing escalated.</p>'
    return ('<div class="wrap"><table><tr><th>Category</th><th>Codes</th><th>What the human needs '
            'to know</th><th>Raised by</th></tr>' + "".join(rows) + "</table></div>")


def _verification(v):
    if v["ok"]:
        parts = [f'<p><span class="good">No mismatches</span>: {v["verified_days"]} days match '
                 'Excel product by product. Line items sum to paid, no duplicates, every invoice '
                 'is still a draft.</p>']
    else:
        parts = [f'<p><span class="bad">Problems found</span>. {v["verified_days"]} days match '
                 'Excel; see below.</p>']
    for d in v["partial_export_days"]:
        parts.append(
            f'<p class="warn">{e(d["date"])}: not fully verified. The Excel export was taken midway '
            f'through this day, so {len(d["unverified_orders"])} orders worth '
            f'{d["unverified_amount"]} are not in it. The covered part reconciles; a fresh export '
            'is needed to check the rest.</p>')
    for d in v["units_mismatch_days"]:
        parts.append(f'<p class="bad">{e(d["date"])}: units mismatch. Vendor {d["vendor_total"]} '
                     f'against Excel {d["excel_total"]}, a ratio of {d["ratio"]}. Escalated, not '
                     'fixed.</p>')
    for d in v["mismatched_days"]:
        parts.append(f'<p class="bad">{e(d["date"])}: {e("; ".join(d["problems"]))}</p>')
    for p in v["global_problems"]:
        parts.append(f'<p class="bad">{e(p)}</p>')
    if v["held_days"]:
        parts.append(f'<p>Still held, safely, with no draft: {e(", ".join(v["held_days"]))}</p>')
    return "".join(parts)


def _timeline(records):
    out = []
    for r in records:
        if r["type"] == "tool_call":
            out.append(f'<details><summary><code>{e(r["tool"])}</code> '
                       f'<span class="muted">{e(json.dumps(r["args"])[:110])}</span></summary>')
        elif r["type"] == "tool_result":
            body = json.dumps(r["result"], indent=1)
            if len(body) > 6000:
                body = body[:6000] + "\n... (full result in transcript.jsonl)"
            out.append(f"<pre>{e(body)}</pre></details>")
        elif r["type"] in ("thinking", "text"):
            out.append(f'<p class="muted">{e(r["text"])}</p>')
    # A call cut off by the budget has no result to close its details element.
    calls = sum(1 for r in records if r["type"] == "tool_call")
    results = sum(1 for r in records if r["type"] == "tool_result")
    return "".join(out) + "</details>" * (calls - results)


def render(ws, live=False):
    v = verify_recovery(ws)
    records = _transcript(ws)
    driver = next((r["driver"] for r in records if r["type"] == "start"), "unknown")
    first = _first_run_counts(ws)
    summary_file = ws.path / "summary.txt"
    summary = summary_file.read_text() if summary_file.exists() else ""
    undo_hint = ("Undo removes the mapping and deletes the drafts built from it, so those days "
                 "return to held." if live else
                 f'Undo buttons work in the live view: <code>python -m report.serve runs/{e(ws.path.name)}'
                 "</code>")
    scripted = ('<div class="banner"><b>Scripted run.</b> A fixed stand-in made these decisions, '
                "not an LLM. It shows the tools and limits, not investigation.</div>"
                if driver.startswith("scripted") else "")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Incident Report</title>
<style>{CSS}</style></head><body>
<h1>Incident report: days held back by unknown codes</h1>
<p class="muted">Driver: {e(driver)}</p>
<div class="banner">Fully simulated, with invented data. This agent is a hackathon build and has
never run against a real system. No confirm capability exists anywhere in it.</div>{scripted}
<div class="stats">
{_stat(first["held"] + first.get("failed", 0), "days without a draft at first")}{_stat(len(v["held_days"]), "days held now")}
{_stat(v["drafts"], "draft invoices")}{_stat(len(active_changes(ws)), "active mappings added")}
{_stat(len(ws.escalations()), "escalations")}</div>
<h2>Summary</h2><div class="summary">{e(summary)}</div>
<h2>Verification</h2>{_verification(v)}
<h2>Mappings applied, with evidence</h2><p class="muted">{undo_hint}</p>{_mappings_table(ws, live)}
{_spacing_section(ws, live)}
<h2>Escalated to a human</h2>{_escalations_table(ws)}
<h2>Every agent action</h2>{_timeline(records)}
</body></html>"""


def write_report(ws):
    path = ws.path / "report.html"
    path.write_text(render(ws))
    return path

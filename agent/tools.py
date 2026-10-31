"""The agent's whole surface. If a capability is not in TOOLS, the agent does not have it.

apply_mapping takes a code and a reason, never a product: the product always comes from a fresh
deterministic proposal, and the policy gate decides whether it may be applied.
"""
from collections import Counter

from job.sync import run_sync
from recovery.detect import classify, last_run_events, units_mismatches
from recovery.policy import check_mapping, check_spacing, detect_period
from recovery.propose import propose_mappings
from recovery.verify import verify_recovery
from sim.vendor import VendorError

ESCALATION_CATEGORIES = ["weak_evidence", "conflicting_evidence", "product_not_in_catalog",
                         "verification_failed", "budget_exhausted", "vendor_failure",
                         "units_mismatch", "other"]
MAX_PROBE_CALLS = 15


def _tool(name, description, properties=None, required=None):
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {"type": "object", "properties": properties or {},
                         "required": required or [], "additionalProperties": False},
    }


_DATE = {"type": "string", "description": "Day as YYYY-MM-DD"}

TOOLS = [
    _tool("read_run_log", "Read-only. Events and failure classification of the latest sync run."),
    _tool("list_unknown_codes", "Read-only. Unknown codes in the latest run, with cups and days."),
    _tool("get_held_day_orders", "Read-only. Vendor orders of one held day: codes and prices only.",
          {"date": _DATE}, ["date"]),
    _tool("get_excel_export", "Read-only. Vendor Excel rows for one day, with names, and when the "
                              "export was taken.", {"date": _DATE}, ["date"]),
    _tool("get_ledger_state", "Read-only. Draft summary per day, held days, and the catalog."),
    _tool("propose_mappings", "Deterministic matching over all orders against the Excel export. "
                              "Returns evidence and conflicts per code. Changes nothing."),
    _tool("apply_mapping", "Add the proposed mapping for one code to the table. The product comes "
                           "from the deterministic proposal; a policy gate may refuse it. "
                           "Recorded as an undoable change.",
          {"code": {"type": "string"},
           "reason": {"type": "string", "description": "Why the evidence is good enough"}},
          ["code", "reason"]),
    _tool("rerun_sync", "Re-run the sync. Days with a draft are skipped; days still containing an "
                        "unknown code stay held."),
    _tool("verify_recovery", "Deterministic check of all drafts against vendor and Excel."),
    _tool("escalate", "Hand a problem to a human with what you found. Use for anything you cannot "
                      "prove.",
          {"category": {"type": "string", "enum": ESCALATION_CATEGORIES},
           "codes": {"type": "array", "items": {"type": "string"}},
           "summary": {"type": "string"}},
          ["category", "codes", "summary"]),
    _tool("probe_api_rate", "Call the rate-limited vendor export a few times at the current spacing "
                            "and report the status of each call. Each call takes 1 second; allow "
                            f"at most {MAX_PROBE_CALLS} calls and 3 probes per incident. Reads only.",
          {"calls": {"type": "integer", "description": f"1 to {MAX_PROBE_CALLS}"}}, ["calls"]),
    _tool("set_call_spacing", "Wait this many seconds before each vendor export call in the sync. "
                              "A policy gate requires evidence from the latest probe. Recorded as "
                              "an undoable change.",
          {"seconds": {"type": "integer"}, "reason": {"type": "string"}}, ["seconds", "reason"]),
    _tool("undo", "Reverse one applied change. For a mapping: removes it and deletes the drafts "
                  "built from it, so those days are held again. For call spacing: restores the "
                  "previous value.",
          {"change_id": {"type": "string"}, "reason": {"type": "string"}},
          ["change_id", "reason"]),
]
TOOL_NAMES = {t["name"] for t in TOOLS}


def all_orders(ws):
    return [o for day in ws.days for o in ws.vendor.list_orders(day)]


def current_proposals(ws):
    """Evidence ignores the agent's own mappings, so it cannot depend on the order they went in."""
    applied = {c["code"] for c in active_changes(ws)}
    base = {code: name for code, name in ws.mapping().items() if code not in applied}
    return propose_mappings(all_orders(ws), ws.export()["rows"], base, ws.ledger.get_catalog())


def active_changes(ws):
    undone = {c["change_id"] for c in ws.changes() if c["type"] == "undo"}
    return [c for c in ws.changes() if c["type"] == "apply_mapping" and c["id"] not in undone]


def active_spacing_changes(ws):
    undone = {c["change_id"] for c in ws.changes() if c["type"] == "undo"}
    return [c for c in ws.changes() if c["type"] == "set_call_spacing" and c["id"] not in undone]


def undo_change(ws, change_id, reason, by):
    spacing = next((c for c in active_spacing_changes(ws) if c["id"] == change_id), None)
    if spacing:
        ws.save_settings({**ws.settings(), "call_spacing": spacing["previous"]})
        ws.add_change({"type": "undo", "id": f"chg-{len(ws.changes()) + 1}", "change_id": change_id,
                       "reason": reason, "by": by})
        return {"undone": True, "call_spacing": spacing["previous"]}
    change = next((c for c in active_changes(ws) if c["id"] == change_id), None)
    if change is None:
        return {"undone": False, "error": f"no active change {change_id}"}
    mapping = ws.mapping()
    mapping.pop(change["code"], None)
    ws.save_mapping(mapping)
    days = [d["date"] for d in ws.ledger.list_drafts() if change["code"] in d["source_codes"]]
    for day in days:
        ws.ledger.delete_draft(day)
    ws.add_change({"type": "undo", "id": f"chg-{len(ws.changes()) + 1}", "change_id": change_id,
                   "code": change["code"], "deleted_drafts": days, "reason": reason, "by": by})
    return {"undone": True, "code": change["code"], "days_held_again": days}


class Toolbox:
    def __init__(self, ws):
        self.ws = ws

    def run(self, name, args):
        if name not in TOOL_NAMES:
            raise ValueError(f"no such tool: {name}")
        spec = next(t for t in TOOLS if t["name"] == name)
        allowed = spec["input_schema"]["properties"]
        extra = set(args) - set(allowed)
        missing = set(spec["input_schema"]["required"]) - set(args)
        if extra or missing:
            raise ValueError(f"bad arguments: unexpected {sorted(extra)}, missing {sorted(missing)}")
        return getattr(self, f"_{name}")(**args)

    def _read_run_log(self):
        events = self.ws.run_log()
        classification = classify(events)
        units = units_mismatches(self.ws.vendor, self.ws.export(), self.ws.days)
        if units:
            classification["units_mismatch"] = len(units)
        return {"classification": classification, "units_mismatch_days": units,
                "events": last_run_events(events)}

    def _list_unknown_codes(self):
        cups, days = Counter(), {}
        for e in last_run_events(self.ws.run_log()):
            for code, n in e.get("codes", {}).items():
                cups[code] += n
                days.setdefault(code, []).append(e["date"])
        return [{"code": c, "cups": n, "days": days[c]} for c, n in sorted(cups.items())]

    def _held_days(self):
        drafted = {d["date"] for d in self.ws.ledger.list_drafts()}
        return [d for d in self.ws.days if d not in drafted]

    def _get_held_day_orders(self, date):
        if date not in self._held_days():
            return {"error": f"{date} is not a held day"}
        return self.ws.vendor.list_orders(date)

    def _get_excel_export(self, date):
        export = self.ws.export()
        return {"exported_date": export["exported_date"], "exported_time": export["exported_time"],
                "rows": [r for r in export["rows"] if r["date"] == date]}

    def _get_ledger_state(self):
        return {
            "drafts": [{"date": d["date"], "status": d["status"], "total": d["total"],
                        "run_id": d["run_id"]} for d in self.ws.ledger.list_drafts()],
            "held_days": self._held_days(),
            "catalog_products": sorted(self.ws.ledger.get_catalog()),
        }

    def _propose_mappings(self):
        result = current_proposals(self.ws)
        mapping = self.ws.mapping()
        for p in result["proposals"]:
            p["policy_blockers"] = check_mapping(p, mapping)
        return result

    def _apply_mapping(self, code, reason):
        mapping = self.ws.mapping()
        proposal = next((p for p in current_proposals(self.ws)["proposals"] if p["code"] == code),
                        None)
        blockers = check_mapping(proposal, mapping)
        if blockers:
            return {"applied": False, "blocked_by_policy": blockers}
        mapping[code] = proposal["product_name"]
        self.ws.save_mapping(mapping)
        change_id = f"chg-{len(self.ws.changes()) + 1}"
        self.ws.add_change({"type": "apply_mapping", "id": change_id, "code": code,
                            "product_name": proposal["product_name"], "evidence": proposal,
                            "reason": reason, "by": "agent"})
        return {"applied": True, "change_id": change_id, "code": code,
                "product_name": proposal["product_name"]}

    def _rerun_sync(self):
        s = run_sync(self.ws)
        return {"run_id": s["run_id"], "created": s["created"], "skipped": len(s["skipped"]),
                "held": s["held"], "failed": s["failed"]}

    def _verify_recovery(self):
        return verify_recovery(self.ws)

    def _escalate(self, category, codes, summary):
        record = {"id": f"esc-{len(self.ws.escalations()) + 1}", "category": category,
                  "codes": codes, "summary": summary, "by": "agent"}
        self.ws.add_escalation(record)
        return {"escalated": True, "id": record["id"]}

    def _probe_api_rate(self, calls):
        if not 1 <= calls <= MAX_PROBE_CALLS:
            return {"error": f"calls must be 1 to {MAX_PROBE_CALLS}"}
        spacing = self.ws.settings()["call_spacing"]
        statuses = []
        for _ in range(calls):
            self.ws.vendor.wait(spacing)
            try:
                self.ws.vendor.export_orders(self.ws.days[0])
                statuses.append(200)
            except VendorError as e:
                statuses.append(e.status)
        period = detect_period(statuses)
        probe = {"spacing": spacing, "statuses": statuses, "period": period,
                 "window_seconds": period * (1 + spacing) if period else None}
        self.ws.add_probe(probe)
        return probe

    def _set_call_spacing(self, seconds, reason):
        probes = self.ws.probes()
        blockers = check_spacing(seconds, probes[-1] if probes else None)
        if blockers:
            return {"applied": False, "blocked_by_policy": blockers}
        previous = self.ws.settings()["call_spacing"]
        self.ws.save_settings({**self.ws.settings(), "call_spacing": seconds})
        change_id = f"chg-{len(self.ws.changes()) + 1}"
        self.ws.add_change({"type": "set_call_spacing", "id": change_id, "seconds": seconds,
                            "previous": previous, "evidence": probes[-1], "reason": reason,
                            "by": "agent"})
        return {"applied": True, "change_id": change_id, "seconds": seconds}

    def _undo(self, change_id, reason):
        return undo_change(self.ws, change_id, reason, by="agent")

"""A fixed stand-in for the LLM: same tools, same gates, no API call.

For tests and offline rehearsal. Its runs are labelled "scripted" everywhere, because they show the
plumbing and the limits but not an LLM investigating.
"""
import json
from types import SimpleNamespace


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_block(id_, name, args):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=args)


def response(blocks, stop_reason="tool_use"):
    return SimpleNamespace(content=blocks, stop_reason=stop_reason)


_CATEGORY = [("catalog", "product_not_in_catalog"), ("conflicts", "conflicting_evidence")]


def _category(blockers):
    for word, category in _CATEGORY:
        if any(word in b for b in blockers):
            return category
    return "weak_evidence"


class ScriptedModel:
    label = "scripted (no LLM)"

    def __init__(self):
        self.step = 0
        self.plan = self._plan()
        self.started = False

    def _last_result(self, messages):
        content = messages[-1]["content"]
        return json.loads(content[-1]["content"]) if isinstance(content, list) else None

    def _call(self, name, args=None):
        self.step += 1
        return [tool_block(f"t{self.step}", name, args or {})]

    def _plan(self):
        log = yield self._call("read_run_log")
        if "vendor_http_500" in log["classification"]:
            probe = yield self._call("probe_api_rate", {"calls": 15})
            if probe["period"]:
                yield self._call("set_call_spacing", {
                    "seconds": probe["window_seconds"] - 1,
                    "reason": f"successes every {probe['period']} calls"})
            yield self._call("rerun_sync")
        yield self._call("list_unknown_codes")
        result = yield self._call("propose_mappings")
        blocks = []
        for p in result["proposals"]:
            self.step += 1
            if p["policy_blockers"]:
                blocks.append(tool_block(f"t{self.step}", "escalate", {
                    "category": _category(p["policy_blockers"]), "codes": [p["code"]],
                    "summary": "; ".join(p["policy_blockers"])}))
            else:
                blocks.append(tool_block(f"t{self.step}", "apply_mapping", {
                    "code": p["code"],
                    "reason": f"{p['cups']} cups across {p['orders']} orders, no conflicts"}))
        if blocks:
            yield blocks
        yield self._call("rerun_sync")
        yield self._call("verify_recovery")

    def respond(self, messages):
        try:
            if self.started:
                blocks = self.plan.send(self._last_result(messages))
            else:
                self.started = True
                blocks = next(self.plan)
        except StopIteration:
            return response([text_block("Scripted run finished. See the report.")], "end_turn")
        return response(blocks)

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
        self.proposals = None

    def _last_result(self, messages):
        content = messages[-1]["content"]
        return json.loads(content[-1]["content"]) if isinstance(content, list) else None

    def respond(self, messages):
        self.step += 1
        ids = f"t{self.step}"
        if self.step == 1:
            return response([tool_block(ids, "read_run_log", {})])
        if self.step == 2:
            return response([tool_block(ids, "list_unknown_codes", {})])
        if self.step == 3:
            return response([tool_block(ids, "propose_mappings", {})])
        if self.step == 4:
            self.proposals = self._last_result(messages)["proposals"]
            blocks = []
            for i, p in enumerate(self.proposals):
                if p["policy_blockers"]:
                    blocks.append(tool_block(f"{ids}-{i}", "escalate", {
                        "category": _category(p["policy_blockers"]), "codes": [p["code"]],
                        "summary": "; ".join(p["policy_blockers"])}))
                else:
                    blocks.append(tool_block(f"{ids}-{i}", "apply_mapping", {
                        "code": p["code"],
                        "reason": f"{p['cups']} cups across {p['orders']} orders, no conflicts"}))
            return response(blocks or [tool_block(ids, "get_ledger_state", {})])
        if self.step == 5:
            return response([tool_block(ids, "rerun_sync", {})])
        if self.step == 6:
            return response([tool_block(ids, "verify_recovery", {})])
        return response([text_block("Scripted run finished. See the report.")], "end_turn")

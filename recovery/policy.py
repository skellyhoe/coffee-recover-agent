"""Limits enforced in code: the gate on every mapping, and the budget on every tool call."""
import hashlib
import json
from dataclasses import dataclass, field

MIN_CUPS = 3
MIN_ORDERS = 2


def check_mapping(proposal, mapping):
    """Returns the list of reasons this proposal may not be applied; empty means allowed."""
    if proposal is None:
        return ["code does not appear as unknown in vendor orders"]
    reasons = []
    if proposal["code"] in mapping:
        reasons.append("code is already mapped")
    if not proposal["product_name"]:
        reasons.append("no single candidate product from the evidence")
    elif not proposal["in_catalog"]:
        reasons.append(f"'{proposal['product_name']}' does not exist in the ledger catalog")
    if proposal["cups"] < MIN_CUPS:
        reasons.append(f"only {proposal['cups']} cups of evidence (minimum {MIN_CUPS})")
    if proposal["orders"] < MIN_ORDERS:
        reasons.append(f"only {proposal['orders']} orders of evidence (minimum {MIN_ORDERS})")
    if proposal["conflicts"]:
        reasons.append(f"conflicts: {proposal['conflicts']}")
    if proposal["price_mismatches"]:
        reasons.append(f"{proposal['price_mismatches']} pairings disagree on price")
    return reasons


class BudgetExhausted(Exception):
    """The incident used up its budget. The run must stop and escalate."""


@dataclass
class IncidentBudget:
    max_calls: int = 40
    tool_limits: dict = field(default_factory=lambda: {
        "rerun_sync": 3, "apply_mapping": 12, "undo": 12, "escalate": 12})
    max_repeats: int = 3
    calls: int = 0
    per_tool: dict = field(default_factory=dict)
    fingerprints: dict = field(default_factory=dict)

    def charge(self, tool):
        """Call before running a tool. Raises if the budget does not allow it."""
        if self.calls >= self.max_calls:
            raise BudgetExhausted(f"used all {self.max_calls} tool calls")
        limit = self.tool_limits.get(tool)
        if limit is not None and self.per_tool.get(tool, 0) >= limit:
            raise BudgetExhausted(f"{tool} reached its limit of {limit} attempts")
        self.calls += 1
        self.per_tool[tool] = self.per_tool.get(tool, 0) + 1

    def record(self, tool, args, result):
        """Call after running a tool. The same call with the same outcome cannot go on repeating."""
        raw = json.dumps([tool, args, result], sort_keys=True, default=str)
        fp = hashlib.sha256(raw.encode()).hexdigest()[:16]
        self.fingerprints[fp] = self.fingerprints.get(fp, 0) + 1
        if self.fingerprints[fp] >= self.max_repeats:
            raise BudgetExhausted(
                f"{tool} repeated {self.fingerprints[fp]} times with no change in outcome")

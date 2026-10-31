"""Limits enforced in code: the gate on every mapping, and the budget on every tool call."""
import hashlib
import json
from dataclasses import dataclass, field

MIN_CUPS = 3
MIN_ORDERS = 2
MAX_CALL_SPACING = 10
MIN_PROBE_SUCCESSES = 3


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


def detect_period(statuses):
    """Calls per success if successes are perfectly regular, else None. 1 means healthy.

    Two successes prove nothing, because any two are evenly spaced. The failures before the first
    success and after the last must also fit the period, so a burst of successes doesn't pass.
    """
    hits = [i for i, s in enumerate(statuses) if s == 200]
    if len(hits) < MIN_PROBE_SUCCESSES:
        return None
    gaps = {b - a for a, b in zip(hits, hits[1:])}
    if len(gaps) != 1:
        return None
    period = gaps.pop()
    if hits[0] >= period or len(statuses) - 1 - hits[-1] >= period:
        return None
    return period


def check_spacing(seconds, probe):
    """Reasons this spacing may not be set; empty means allowed. Needs a probe to justify it."""
    if probe is None:
        return ["no probe evidence: run probe_api_rate first"]
    if probe["period"] is None:
        successes = probe["statuses"].count(200)
        if successes < MIN_PROBE_SUCCESSES:
            return [f"the latest probe has only {successes} successes and {MIN_PROBE_SUCCESSES} are "
                    "needed to prove a pattern, so this is not proven either way"]
        return ["the latest probe's successes are not evenly spaced, so this is not a simple "
                "rate limit"]
    if probe["period"] == 1:
        return ["the latest probe shows calls already succeeding"]
    needed = probe["window_seconds"] - 1
    reasons = []
    if seconds < needed:
        reasons.append(f"{seconds}s is below the {needed}s the probe shows is needed")
    if seconds > MAX_CALL_SPACING:
        reasons.append(f"{seconds}s is above the maximum of {MAX_CALL_SPACING}s")
    if needed > MAX_CALL_SPACING:
        reasons.append(f"the probe needs {needed}s, above the maximum of {MAX_CALL_SPACING}s")
    return reasons


class BudgetExhausted(Exception):
    """The incident used up its budget. The run must stop and escalate."""


@dataclass
class IncidentBudget:
    max_calls: int = 60
    tool_limits: dict = field(default_factory=lambda: {
        "rerun_sync": 3, "apply_mapping": 12, "undo": 12, "escalate": 12,
        "probe_api_rate": 3, "set_call_spacing": 3})
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

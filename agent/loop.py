"""Plain tool-use loop. The LLM decides what to do; the budget and gates decide what it may do."""
import json
import os

from agent.tools import TOOLS, Toolbox
from recovery.policy import BudgetExhausted, IncidentBudget
from recovery.verify import verify_recovery

MODEL = os.environ.get("RECOVERY_MODEL", "claude-sonnet-5-5")
MAX_TURNS = 30

SYSTEM = """You are a recovery agent for a simulated daily sync. The sync reads coffee machine orders \
from a vendor API and creates one itemized draft invoice per day in a ledger. A human reviews every \
draft afterwards; that step is not yours and you have no tool for it.

The vendor API identifies products only by opaque code. Our table maps code to product. A day with \
an unknown code is held back whole. The vendor's Excel export has names, and is an independent source.

Work through the incident:
1. Detect: read the run log and classify what went wrong.
2. Diagnose: list the unknown codes, run propose_mappings, and look at raw orders and Excel rows \
where the evidence is thin or something does not add up.
3. Fix: apply_mapping only for codes whose evidence you can defend. A policy gate has the last word, \
and being allowed by the gate does not oblige you to apply. Elimination is a sound method when the \
code it depends on is itself well proven: it is part of the manual procedure this replaces.
If the log shows vendor errors, look for a pattern in the vendor_call numbers and test it with \
probe_api_rate before set_call_spacing. A pattern you cannot prove, or spacing that does not help, \
goes to a human. A units mismatch is never yours to fix, because you cannot change prices: escalate \
it with the day totals.
4. Rerun the sync, then run verify_recovery.
5. Investigate any leftover mismatch. If a change turns out wrong, undo it.
6. Escalate each code you could not prove, with the evidence and what a human should check. Say \
what you do not know; do not guess. A code left unmapped keeps its days held, which is the safe state.

Amounts are integers in minor units with no currency; report them that way. When you state counts of \
cups or orders, take them from propose_mappings, not from the days you sampled.

Limits: 60 tool calls per incident, and an identical call with an identical outcome may run only \
twice; a third ends the run. Prefer evidence from propose_mappings and sample raw days rather than \
reading all of them. When a step is not making progress, escalate rather than retry.
Finish with a short plain-language summary for the on-call reader: what was wrong, what you changed, \
what you verified and how, what you escalated and why, and what is still unverified."""


class ModelUnavailable(Exception):
    pass


class AnthropicModel:
    """Real LLM. Credentials are resolved by the SDK from the environment."""

    def __init__(self, model=MODEL, effort=os.environ.get("RECOVERY_EFFORT", "medium")):
        import anthropic

        self._errors = anthropic.APIError
        self._client = anthropic.Anthropic()
        self.model = model
        self.effort = effort
        self.label = f"llm:{model}"

    def respond(self, messages):
        try:
            return self._client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                cache_control={"type": "ephemeral"},
                system=SYSTEM,
                tools=TOOLS,
                messages=messages,
                thinking={"type": "adaptive", "display": "summarized"},
                output_config={"effort": self.effort},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except self._errors as e:
            raise ModelUnavailable(str(e)) from e


class Transcript:
    def __init__(self, ws, label):
        self.path = ws.path / "transcript.jsonl"
        self.path.write_text("")
        self.write({"type": "start", "driver": label})

    def write(self, record):
        with open(self.path, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")


def _system_escalation(ws, category, codes, summary):
    ws.add_escalation({"id": f"esc-{len(ws.escalations()) + 1}", "category": category,
                       "codes": codes, "summary": summary, "by": "system"})


def close_incident(ws, transcript, stop_reason=None):
    """Runs whatever the model did: nothing may end silently."""
    if stop_reason:
        _system_escalation(ws, "budget_exhausted", [], f"Agent run stopped: {stop_reason}")
    verification = verify_recovery(ws)
    units = verification["units_mismatch_days"]
    units_days = {d["date"] for d in units}
    if units and not any(e["category"] == "units_mismatch" for e in ws.escalations()):
        _system_escalation(ws, "units_mismatch", [],
                           f"Vendor totals are about 100x off from Excel: {units}")
    other_days = [d for d in verification["mismatched_days"] if d["date"] not in units_days]
    if other_days or verification["global_problems"]:
        _system_escalation(ws, "verification_failed", [],
                           f"Verifier reports problems: {other_days} "
                           f"{verification['global_problems']}")
    covered = {c for e in ws.escalations() for c in e["codes"]}
    mapping = ws.mapping()
    unexplained = [day for day in verification["held_days"] if day not in units_days
                   and all(c["code"] in mapping for o in ws.vendor.list_orders(day)
                          for c in o["cups"])]
    if unexplained and not any(e["category"] == "vendor_failure" for e in ws.escalations()):
        _system_escalation(ws, "vendor_failure", [],
                           f"No draft and no unknown code, so the vendor export is the likely "
                           f"cause: {unexplained}")
    left = sorted({c["code"] for day in verification["held_days"]
                   for o in ws.vendor.list_orders(day) for c in o["cups"]
                   if c["code"] not in mapping} - covered)
    if left:
        _system_escalation(ws, "other", left,
                           "Still unknown when the run ended and not escalated by the agent.")
    transcript.write({"type": "closed", "verification": verification,
                      "escalations": ws.escalations()})
    return verification


def run_agent(ws, model, budget=None, max_turns=MAX_TURNS):
    budget = budget or IncidentBudget()
    toolbox = Toolbox(ws)
    transcript = Transcript(ws, model.label)
    opening = ("Alert from the daily sync: days were held back or failed. Latest run summary: "
               + json.dumps(ws.run_log()[-1]) + " Investigate and recover what you can prove.")
    messages = [{"role": "user", "content": opening}]
    transcript.write({"type": "alert", "text": opening})
    stop_reason, summary = None, ""
    usage = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}

    for turn in range(max_turns):
        try:
            response = model.respond(messages)
        except ModelUnavailable as e:
            stop_reason = f"model unavailable: {e}"
            break

        if used := getattr(response, "usage", None):
            usage["input"] += used.input_tokens
            usage["cache_write"] += used.cache_creation_input_tokens or 0
            usage["cache_read"] += used.cache_read_input_tokens or 0
            usage["output"] += used.output_tokens

        for block in response.content:
            if block.type == "thinking" and block.thinking:
                transcript.write({"type": "thinking", "turn": turn, "text": block.thinking})
            elif block.type == "text" and block.text:
                transcript.write({"type": "text", "turn": turn, "text": block.text})
                summary = block.text

        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue
        if response.stop_reason != "tool_use":
            if response.stop_reason != "end_turn":
                stop_reason = f"model stopped with {response.stop_reason}"
            break

        messages.append({"role": "assistant", "content": response.content})
        results = []
        try:
            for block in response.content:
                if block.type != "tool_use":
                    continue
                transcript.write({"type": "tool_call", "turn": turn, "tool": block.name,
                                  "args": block.input})
                budget.charge(block.name)
                try:
                    result, is_error = toolbox.run(block.name, block.input), False
                except (ValueError, TypeError) as e:
                    result, is_error = {"error": str(e)}, True
                transcript.write({"type": "tool_result", "turn": turn, "tool": block.name,
                                  "result": result, "is_error": is_error})
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": json.dumps(result), "is_error": is_error})
                budget.record(block.name, block.input, result)
        except BudgetExhausted as e:
            stop_reason = str(e)
            break
        messages.append({"role": "user", "content": results})
    else:
        stop_reason = f"used all {max_turns} turns"

    transcript.write({"type": "usage", **usage})
    verification = close_incident(ws, transcript, stop_reason)
    return {"stop_reason": stop_reason, "summary": summary, "verification": verification,
            "calls": budget.calls, "usage": usage}

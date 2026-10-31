"""Proves no path to confirming an invoice exists: routes, ledger API, agent tools, source tree."""
import ast
import inspect
import re
from pathlib import Path

from sim import ledger as ledger_module
from sim.ledger import ROUTES, Ledger

ROOT = Path(__file__).resolve().parent.parent
BANNED = re.compile(r"confirm|finali[sz]e|approve|submit|credit_?note|tax", re.I)
SOURCE_DIRS = ["sim", "job", "recovery", "agent", "scenarios", "report", "eval"]


def source_files():
    return [p for d in SOURCE_DIRS for p in (ROOT / d).rglob("*.py")]


def test_ledger_routes_have_no_confirm_endpoint():
    assert set(ROUTES) == {"GET /catalog", "GET /drafts", "POST /drafts", "DELETE /drafts/{date}"}
    assert not [r for r in ROUTES if BANNED.search(r)]


def test_ledger_public_api_is_exactly_the_routes():
    public = {n for n, _ in inspect.getmembers(Ledger, inspect.isfunction) if not n.startswith("_")}
    assert public == set(ROUTES.values())


def test_a_draft_can_only_ever_be_a_draft(tmp_path):
    led = Ledger(tmp_path / "l.json", {})
    assert "status" not in inspect.signature(Ledger.create_draft).parameters
    assert led.create_draft("2026-09-01", [], [], [], "r")["status"] == "draft"
    src = inspect.getsource(ledger_module)
    assert re.findall(r'"status":\s*("[^"]*")', src) == ['"draft"']


def test_no_identifier_anywhere_can_confirm():
    offenders = []
    for path in source_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            name = None
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                name = node.name
            elif isinstance(node, ast.Attribute):
                name = node.attr
            elif isinstance(node, ast.Name):
                name = node.id
            if name and BANNED.search(name):
                offenders.append(f"{path.name}:{name}")
    assert not offenders, offenders


def test_only_draft_writes_reach_the_ledger():
    """Only the sync creates drafts and only undo deletes them; nothing else writes."""
    for path in source_files():
        text = path.read_text()
        if ".create_draft(" in text:
            assert path.name == "sync.py", path
        if ".delete_draft(" in text:
            assert path.name == "tools.py", path

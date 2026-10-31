"""Fake ledger. It holds draft invoices only.

A human finishes a draft elsewhere; this API offers no way to do it. Deleting is allowed because a
draft has no effect outside the ledger, and that is what makes agent changes undoable.
"""
import json
from pathlib import Path

ROUTES = {
    "GET /catalog": "get_catalog",
    "GET /drafts": "list_drafts",
    "POST /drafts": "create_draft",
    "DELETE /drafts/{date}": "delete_draft",
}


class DuplicateDraft(Exception):
    pass


class Ledger:
    def __init__(self, path, catalog=None):
        self._path = Path(path)
        if self._path.exists():
            self._data = json.loads(self._path.read_text())
        else:
            self._data = {"catalog": catalog or {}, "drafts": {}}
            self._save()

    def _save(self):
        self._path.write_text(json.dumps(self._data, indent=1))

    def get_catalog(self):
        return dict(self._data["catalog"])

    def list_drafts(self):
        return list(self._data["drafts"].values())

    def create_draft(self, day, lines, order_ids, source_codes, run_id):
        if day in self._data["drafts"]:
            raise DuplicateDraft(day)
        draft = {
            "date": day,
            "status": "draft",
            "lines": lines,
            "total": sum(l["amount"] for l in lines),
            "order_ids": order_ids,
            "source_codes": source_codes,
            "run_id": run_id,
        }
        self._data["drafts"][day] = draft
        self._save()
        return draft

    def delete_draft(self, day):
        removed = self._data["drafts"].pop(day, None)
        self._save()
        return removed

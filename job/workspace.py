"""One run directory: the simulated systems plus our own state, all as plain files."""
import json
from pathlib import Path

from sim.excel import read_export, write_export
from sim.ledger import Ledger
from sim.vendor import VendorAPI


class Workspace:
    def __init__(self, path):
        self.path = Path(path)
        self.world = json.loads((self.path / "world.json").read_text())
        self.vendor = VendorAPI(self.world)
        self.ledger = Ledger(self.path / "ledger.json")

    @classmethod
    def create(cls, path, world):
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        (path / "world.json").write_text(json.dumps(world))
        (path / "mapping.json").write_text(json.dumps(world["mapping"], indent=1))
        Ledger(path / "ledger.json", world["catalog"])
        write_export(world, path / "export.xlsx")
        return cls(path)

    @property
    def days(self):
        return self.world["days"]

    def mapping(self):
        return json.loads((self.path / "mapping.json").read_text())

    def save_mapping(self, mapping):
        (self.path / "mapping.json").write_text(json.dumps(mapping, indent=1))

    def settings(self):
        p = self.path / "settings.json"
        return json.loads(p.read_text()) if p.exists() else {"call_spacing": 0}

    def save_settings(self, settings):
        (self.path / "settings.json").write_text(json.dumps(settings, indent=1))

    def export(self):
        return read_export(self.path / "export.xlsx")

    def _append(self, name, record):
        with open(self.path / name, "a") as f:
            f.write(json.dumps(record) + "\n")

    def _read(self, name):
        p = self.path / name
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def log(self, record):
        self._append("run_log.jsonl", record)

    def run_log(self):
        return self._read("run_log.jsonl")

    def add_probe(self, record):
        self._append("probes.jsonl", record)

    def probes(self):
        return self._read("probes.jsonl")

    def add_change(self, record):
        self._append("changes.jsonl", record)

    def changes(self):
        return self._read("changes.jsonl")

    def add_escalation(self, record):
        self._append("escalations.jsonl", record)

    def escalations(self):
        return self._read("escalations.jsonl")

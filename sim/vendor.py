"""Fake vendor API. Read-only, and identifies products by opaque code only.

export_orders is what the sync calls, and is the endpoint that can be rate limited. list_orders is
the order-details lookup used for diagnosis and verification, and is never limited here.

A fault in world["vendor_fault"] makes export_orders answer HTTP 500 unless the call is allowed:
  mode "clock": allowed once per `period` seconds of simulated time, so spacing calls fixes it.
  mode "count": allowed on every `period`th call, whatever the spacing.
Each call takes 1 simulated second, so unspaced calls succeed on exactly every 5th.

world["units_fault"] = {"days": [...], "factor": 100} makes the vendor silently send prices on those
days in the wrong unit: nothing errors, and only the independent Excel export shows it.
"""
from sim.generator import order_total


class VendorError(Exception):
    def __init__(self, status, call):
        super().__init__(f"HTTP {status} on call {call}")
        self.status = status
        self.call = call


class VendorAPI:
    def __init__(self, world):
        self._orders = world["orders"]
        self._fault = world.get("vendor_fault")
        self._units = world.get("units_fault") or {"days": [], "factor": 1}
        self.calls = 0
        self._clock = 0
        self._last_ok = 0

    def wait(self, seconds):
        self._clock += seconds

    def list_orders(self, day):
        return [self._public(o) for o in self._orders if o["date"] == day]

    def export_orders(self, day):
        self.calls += 1
        self._clock += 1
        if self._fault and not self._allowed():
            raise VendorError(500, self.calls)
        self._last_ok = self._clock
        return self.list_orders(day)

    def _allowed(self):
        period = self._fault["period"]
        if self._fault["mode"] == "count":
            return self.calls % period == 0
        return self._clock - self._last_ok >= period

    def _public(self, order):
        factor = self._units["factor"] if order["date"] in self._units["days"] else 1
        return {
            "id": order["id"],
            "date": order["date"],
            "time": order["time"],
            "paid": order_total(order) * factor,
            "cups": [{"code": c["code"], "price": c["price"] * factor} for c in order["cups"]],
        }

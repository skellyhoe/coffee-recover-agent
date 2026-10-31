"""Fake vendor API. Read-only, and identifies products by opaque code only."""
from sim.generator import order_total


class VendorAPI:
    def __init__(self, world):
        self._orders = world["orders"]

    def list_orders(self, day):
        return [self._public(o) for o in self._orders if o["date"] == day]

    @staticmethod
    def _public(order):
        return {
            "id": order["id"],
            "date": order["date"],
            "time": order["time"],
            "paid": order_total(order),
            "cups": [{"code": c["code"], "price": c["price"]} for c in order["cups"]],
        }

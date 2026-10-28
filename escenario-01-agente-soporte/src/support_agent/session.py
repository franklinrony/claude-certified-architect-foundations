"""Hechos del caso que no deben perderse dentro de un resumen."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionState:
    verified_customer_id: str | None = None
    customer_name: str | None = None
    account_status: str | None = None
    match_count: int | None = None
    orders: list[dict[str, Any]] = field(default_factory=list)
    refunds: list[dict[str, Any]] = field(default_factory=list)
    handoffs: list[dict[str, Any]] = field(default_factory=list)

    def remember_customer(self, data: dict[str, Any]) -> None:
        matches = data.get("matches") or []
        self.match_count = len(matches)
        if data.get("verified") and len(matches) == 1:
            match = matches[0]
            self.verified_customer_id = match["customer_id"]
            self.customer_name = match["name"]
            self.account_status = match["account_status"]
            return
        self.verified_customer_id = None
        self.customer_name = None
        self.account_status = None

    def remember_orders(self, orders: list[dict[str, Any]]) -> None:
        by_id = {order["order_id"]: order for order in self.orders}
        for order in orders:
            by_id[order["order_id"]] = order
        self.orders = list(by_id.values())

    def remember_refund(self, data: dict[str, Any]) -> None:
        self.refunds.append(
            {
                "refund_id": data["refund_id"],
                "order_id": data["order_id"],
                "customer_id": data["customer_id"],
                "amount": data["amount"],
                "currency": data["currency"],
            }
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "verified_customer_id": self.verified_customer_id,
            "customer_name": self.customer_name,
            "account_status": self.account_status,
            "match_count": self.match_count,
            "orders": [dict(order) for order in self.orders],
            "refunds": [dict(refund) for refund in self.refunds],
        }

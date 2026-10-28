"""Normaliza salidas heterogéneas antes de que el modelo las acumule en contexto.

La función es idempotente: un pedido ya normalizado sale igual.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


STATUS_BY_CODE = {1: "placed", 2: "shipped", 3: "delivered"}


def normalize_order(raw: dict[str, Any]) -> dict[str, Any]:
    status_code = raw.get("status_code", raw.get("status"))
    if isinstance(status_code, int):
        status = STATUS_BY_CODE.get(status_code, f"unknown_{status_code}")
    elif status_code is None:
        status = None
    else:
        status = str(status_code)

    placed_at = raw.get("placed_at")
    if isinstance(placed_at, (int, float)):
        placed = datetime.fromtimestamp(int(placed_at), timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    elif placed_at is None:
        placed = None
    else:
        placed = str(placed_at)

    items = []
    for item in raw.get("items") or []:
        items.append({"name": item.get("name"), "qty": item.get("qty")})

    return {
        "order_id": raw.get("order_id"),
        "customer_id": raw.get("customer_id"),
        "status": status,
        "total": None if raw.get("total") is None else str(raw["total"]),
        "currency": raw.get("currency"),
        "placed_at": placed,
        "return_window_open": bool(raw.get("return_window_open")),
        "refunded": bool(raw.get("refunded")),
        "items": items,
    }

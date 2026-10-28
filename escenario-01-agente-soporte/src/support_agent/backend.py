"""Pedidos y clientes en PostgreSQL, esquema escenario_01."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from support_agent.db import TransientStoreError, connect


SCHEMA = "escenario_01"


class SupportBackend:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    @classmethod
    def connect(cls) -> SupportBackend:
        return cls(connect())

    def close(self) -> None:
        self.conn.close()

    def fetch_all(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> list[dict[str, Any]]:
        try:
            cursor = self.conn.execute(sql, params)
        except (psycopg.errors.QueryCanceled, psycopg.OperationalError) as exc:
            self.conn.rollback()
            raise TransientStoreError("database timeout") from exc
        if cursor.description is None:
            return []
        return list(cursor.fetchall())

    def customers_by_email(self, email: str) -> list[dict[str, Any]]:
        return self.fetch_all(
            f"""
            SELECT customer_id, email, full_name AS name, account_status
            FROM {SCHEMA}.customers
            WHERE lower(email) = lower(%s)
            ORDER BY customer_id
            """,
            (email.strip(),),
        )

    def customer_by_id(self, customer_id: str) -> dict[str, Any] | None:
        rows = self.fetch_all(
            f"""
            SELECT customer_id, email, full_name AS name, account_status
            FROM {SCHEMA}.customers
            WHERE customer_id = %s
            """,
            (customer_id,),
        )
        return rows[0] if rows else None

    def orders_for(self, *, order_id: str | None, customer_id: str | None) -> list[dict[str, Any]]:
        filters: list[str] = []
        params: list[str] = []
        if order_id:
            filters.append("o.order_id = %s")
            params.append(order_id)
        if customer_id:
            filters.append("o.customer_id = %s")
            params.append(customer_id)
        if not filters:
            return []
        rows = self.fetch_all(
            f"""
            SELECT
                o.order_id,
                o.customer_id,
                o.status_code,
                o.placed_at,
                o.source_channel,
                o.total,
                o.currency,
                (o.placed_at + make_interval(days => o.return_window_days))
                    >= statement_timestamp() AS return_window_open,
                EXISTS (
                    SELECT 1 FROM {SCHEMA}.refunds AS prior
                    WHERE prior.order_id = o.order_id
                ) AS refunded,
                pay.payment_token,
                ship.line1 || ', ' || ship.city AS shipping_address
            FROM {SCHEMA}.orders AS o
            JOIN {SCHEMA}.payments AS pay ON pay.order_id = o.order_id
            JOIN {SCHEMA}.shipments AS ship ON ship.order_id = o.order_id
            WHERE {" AND ".join(filters)}
            ORDER BY o.order_id
            """,
            params,
        )
        if not rows:
            return []
        items = self.fetch_all(
            f"""
            SELECT order_id, sku, product_name AS name, qty, warehouse_code AS warehouse
            FROM {SCHEMA}.order_items
            WHERE order_id = ANY(%s)
            ORDER BY order_id, sku
            """,
            ([row["order_id"] for row in rows],),
        )
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            grouped.setdefault(item["order_id"], []).append(
                {
                    "sku": item["sku"],
                    "name": item["name"],
                    "qty": item["qty"],
                    "warehouse": item["warehouse"],
                }
            )
        return [self._pack_order(row, grouped.get(row["order_id"], [])) for row in rows]

    def order_by_id(self, order_id: str) -> dict[str, Any] | None:
        rows = self.orders_for(order_id=order_id, customer_id=None)
        return rows[0] if rows else None

    def refund_ids(self) -> list[str]:
        rows = self.fetch_all(
            f"SELECT refund_id FROM {SCHEMA}.refunds ORDER BY refund_id"
        )
        return [row["refund_id"] for row in rows]

    def issue_refund(
        self,
        *,
        customer_id: str,
        order_id: str,
        amount: Decimal,
        reason: str,
    ) -> dict[str, Any]:
        try:
            with self.conn.transaction():
                row = self.conn.execute(
                    f"""
                    SELECT
                        o.order_id,
                        o.customer_id,
                        o.total,
                        o.currency,
                        (o.placed_at + make_interval(days => o.return_window_days))
                            >= statement_timestamp() AS return_window_open,
                        EXISTS (
                            SELECT 1 FROM {SCHEMA}.refunds AS prior
                            WHERE prior.order_id = o.order_id
                        ) AS refunded
                    FROM {SCHEMA}.orders AS o
                    WHERE o.order_id = %s
                    FOR UPDATE
                    """,
                    (order_id,),
                ).fetchone()
                if row is None or row["customer_id"] != customer_id:
                    return {"status": "not_found"}
                if row["refunded"]:
                    return {
                        "status": "already_refunded",
                        "total": row["total"],
                        "currency": row["currency"],
                    }
                if not row["return_window_open"]:
                    return {
                        "status": "window_closed",
                        "total": row["total"],
                        "currency": row["currency"],
                    }
                if str(row["currency"]).strip() != "USD":
                    return {
                        "status": "currency",
                        "total": row["total"],
                        "currency": str(row["currency"]).strip(),
                    }
                if amount > row["total"]:
                    return {
                        "status": "exceeds_total",
                        "total": row["total"],
                        "currency": row["currency"],
                    }
                refund_id = f"ref_{order_id}"
                self.conn.execute(
                    f"""
                    INSERT INTO {SCHEMA}.refunds
                        (refund_id, order_id, customer_id, amount, currency, reason)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (refund_id, order_id, customer_id, amount, row["currency"], reason),
                )
                return {
                    "status": "ok",
                    "refund_id": refund_id,
                    "order_id": order_id,
                    "customer_id": customer_id,
                    "amount": amount,
                    "currency": str(row["currency"]).strip(),
                }
        except (psycopg.errors.QueryCanceled, psycopg.OperationalError) as exc:
            raise TransientStoreError("database timeout") from exc

    def record_handoff(self, handoff: dict[str, Any]) -> None:
        amount = handoff.get("refund_amount")
        owns_transaction = self.conn.info.transaction_status == TransactionStatus.IDLE
        self.conn.execute(
            f"""
            INSERT INTO {SCHEMA}.handoffs
                (customer_id, order_id, refund_amount, root_cause, reason,
                 recommended_action, case_facts)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                handoff.get("customer_id"),
                handoff.get("order_id"),
                None if amount in (None, "") else amount,
                handoff.get("root_cause"),
                handoff["reason"],
                handoff["recommended_action"],
                Jsonb(handoff.get("caseFacts") or {}),
            ),
        )
        if owns_transaction:
            self.conn.commit()

    def handoff_for_order(self, order_id: str | None) -> dict[str, Any] | None:
        if not order_id:
            return None
        rows = self.fetch_all(
            f"""
            SELECT handoff_id::text AS handoff_id,
                   customer_id,
                   order_id,
                   refund_amount::text AS refund_amount,
                   root_cause,
                   reason,
                   recommended_action,
                   created_at
            FROM {SCHEMA}.handoffs
            WHERE order_id = %s
            ORDER BY handoff_id
            LIMIT 1
            """,
            (order_id,),
        )
        if not rows:
            return None
        row = dict(rows[0])
        created = row.get("created_at")
        if hasattr(created, "isoformat"):
            row["created_at"] = created.isoformat()
        return row

    def handoff_count(self) -> int:
        rows = self.fetch_all(f"SELECT count(*) AS n FROM {SCHEMA}.handoffs")
        return int(rows[0]["n"])

    def _pack_order(self, row: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
        placed = row["placed_at"]
        if row["source_channel"] == "legacy":
            placed_out: int | str = int(placed.timestamp())
        else:
            placed_out = _iso(placed)
        return {
            "order_id": row["order_id"],
            "customer_id": row["customer_id"],
            "status_code": int(row["status_code"]),
            "placed_at": placed_out,
            "total": str(row["total"]),
            "currency": str(row["currency"]).strip(),
            "return_window_open": bool(row["return_window_open"]),
            "refunded": bool(row["refunded"]),
            "payment_token": row["payment_token"],
            "shipping_address": row["shipping_address"],
            "items": items,
        }


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

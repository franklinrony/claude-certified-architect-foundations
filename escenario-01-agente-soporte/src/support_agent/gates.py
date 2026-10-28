"""Gates deterministas. Identidad y tope de reembolso no dependen del prompt."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from support_agent.backend import SupportBackend
from support_agent.db import TransientStoreError
from support_agent.errors import fail
from support_agent.session import SessionState


AUTO_REFUND_LIMIT = Decimal("500.00")


def short_tool_name(tool_name: str) -> str:
    return tool_name.split("__")[-1]


def parse_amount(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite():
        return None
    return amount


def lookup_precondition(
    session: SessionState,
    arguments: dict[str, Any],
) -> dict[str, Any] | None:
    """None deja pasar lookup_order. Sin identidad verificada, la lectura no corre."""
    query = {
        "order_id": (arguments.get("order_id") or "").strip() or None,
        "customer_id": (arguments.get("customer_id") or "").strip() or None,
    }
    if session.verified_customer_id is None:
        return fail(
            "lookup_order",
            "permission",
            False,
            "Identity is not verified. Call get_customer and get exactly one "
            "active match before lookup_order.",
            query,
        )
    if query["customer_id"] and query["customer_id"] != session.verified_customer_id:
        return fail(
            "lookup_order",
            "permission",
            False,
            "customer_id does not match the verified customer "
            f"{session.verified_customer_id}.",
            query,
        )
    return None


def refund_precondition(
    session: SessionState,
    arguments: dict[str, Any],
) -> dict[str, Any] | None:
    """None significa que el hook deja pasar la llamada.

    El tool sigue pudiendo rechazar ventana de devolución, pedido inexistente
    o un reembolso ya hecho. Esas son reglas de dominio, no el gate de dinero.
    """
    amount = parse_amount(arguments.get("amount"))
    customer_id = arguments.get("customer_id")
    query = {
        "customer_id": customer_id,
        "order_id": arguments.get("order_id"),
        "amount": arguments.get("amount"),
    }

    if session.verified_customer_id is None:
        return fail(
            "process_refund",
            "permission",
            False,
            "Identity is not verified. Call get_customer and get exactly one "
            "active match before process_refund.",
            query,
        )

    if customer_id != session.verified_customer_id:
        return fail(
            "process_refund",
            "permission",
            False,
            "customer_id does not match the verified customer "
            f"{session.verified_customer_id}.",
            query,
        )

    if session.account_status != "active":
        return fail(
            "process_refund",
            "permission",
            False,
            f"Account status is {session.account_status}. Refunds are blocked.",
            query,
        )

    if amount is None or amount <= 0:
        return None

    if amount > AUTO_REFUND_LIMIT:
        return fail(
            "process_refund",
            "business",
            False,
            f"Refund of {amount} USD exceeds the {AUTO_REFUND_LIMIT} automatic "
            "limit. Call escalate_to_human with the case facts. Do not retry.",
            query,
        )

    return None


def public_customer(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "customer_id": row["customer_id"],
        "email": row["email"],
        "name": row["name"],
        "account_status": row["account_status"],
    }


def find_customers(backend: SupportBackend, arguments: dict[str, Any]) -> list[dict[str, Any]] | dict[str, Any]:
    email = (arguments.get("email") or "").strip()
    customer_id = (arguments.get("customer_id") or "").strip()
    query = {"email": email or None, "customer_id": customer_id or None}
    if not email and not customer_id:
        return fail(
            "get_customer",
            "validation",
            False,
            "Provide email or customer_id.",
            query,
        )
    try:
        if customer_id:
            row = backend.customer_by_id(customer_id)
            return [] if row is None else [row]
        return backend.customers_by_email(email)
    except TransientStoreError:
        return fail(
            "get_customer",
            "transient",
            True,
            "Customer lookup timed out. Retry the same query.",
            query,
        )

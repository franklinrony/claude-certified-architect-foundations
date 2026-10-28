"""Contratos y ejecución de las tools del escenario 1.

El examen nombra cuatro: get_customer, lookup_order, process_refund y
escalate_to_human. lookup_handoff es local: mira si el pedido ya tiene ticket
y no inserta otra fila. Las descripciones dicen qué entra, qué sale, cuándo
usarlas y cuándo no.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from support_agent.backend import SupportBackend
from support_agent.db import TransientStoreError
from support_agent.errors import fail, ok
from support_agent.gates import (
    AUTO_REFUND_LIMIT,
    find_customers,
    parse_amount,
    public_customer,
    lookup_precondition,
    refund_precondition,
    short_tool_name,
)
from support_agent.session import SessionState


TOOL_NAMES = (
    "get_customer",
    "lookup_order",
    "process_refund",
    "lookup_handoff",
    "escalate_to_human",
)

ALREADY_OPEN_MESSAGE = (
    "A handoff ticket already exists for this order. Do not create another. "
    "Tell the customer to wait, or to contact support and mention the existing ticket."
)


GET_CUSTOMER_DESCRIPTION = """
Identify the customer before any account or money action.

Pass email or customer_id. One is enough.

Returns every match. Zero matches is a successful empty result, not a failure.
If more than one customer matches, ask for another identifier. Do not pick one.
An account_status other than "active" is not a verified identity for refunds.

Does not look up orders, issue refunds, or contact a human.

Example: {"email": "ana@example.test"} returns one active customer.
Example: {"email": "shared@example.test"} returns two customers. Do not refund yet.
""".strip()


LOOKUP_ORDER_DESCRIPTION = """
Read orders for a return or billing question.

Pass order_id or customer_id. One is enough. A PreToolUse hook blocks this
tool until get_customer has verified exactly one active customer. That block
is not retryable. The raw backend payload is normalized after the call:
status codes become names, unix timestamps become ISO-8601, and payment
tokens, addresses, SKUs, and warehouse ids are dropped.

Zero orders is a successful empty result, not a failure.

Does not verify identity, move money, or escalate.

Example: {"order_id": "ord_10"} returns that order's return-relevant fields.
Example: {"customer_id": "cus_100"} returns every order for that customer.
""".strip()


PROCESS_REFUND_DESCRIPTION = """
Issue a refund for one order after identity is already verified.

Required: customer_id, order_id, amount, reason. amount is a decimal string
in USD, such as "42.50".

A PreToolUse hook blocks this tool until get_customer has verified exactly
one active customer in this session, and blocks amounts over 500 USD. Those
blocks are not retryable. Over the limit, call escalate_to_human.

This tool does not search for the customer. A closed return window, an unknown
order, or an order already refunded comes back as a business error.

Example: {"customer_id": "cus_100", "order_id": "ord_10", "amount": "42.50", "reason": "damaged on arrival"}
""".strip()


ESCALATE_TO_HUMAN_DESCRIPTION = """
Hand the case to a person who will not see this transcript.

Use it when the customer explicitly asks for a human, a policy gap blocks the
action (including a refund over 500 USD), or you cannot make progress after
the relevant lookups. Do not use it only because the customer sounds upset
and the case is straightforward.

Required: reason, recommended_action. Include customer_id, order_id,
refund_amount, and root_cause when you know them. Copy amounts, dates, and
ids from caseFacts. Do not round them and do not drop them.

Example: the hook denied a 780.00 USD refund, so escalate with that amount,
the order id, and recommended_action "approve or reject the exception".

If lookup_handoff already found a ticket for that order, do not call this tool.
A second call does not create another row.
""".strip()


LOOKUP_HANDOFF_DESCRIPTION = """
Check whether a handoff ticket already exists for one order.

Pass order_id. One ticket per order. This tool does not create a ticket,
move money, or contact a human.

Zero tickets is a successful empty result, not a failure.
If a ticket exists, tell the customer to wait or to contact support and
mention that ticket. Do not call escalate_to_human again for that order.

Example: {"order_id": "ord_11"}
""".strip()


DESCRIPTIONS = {
    "get_customer": GET_CUSTOMER_DESCRIPTION,
    "lookup_order": LOOKUP_ORDER_DESCRIPTION,
    "process_refund": PROCESS_REFUND_DESCRIPTION,
    "lookup_handoff": LOOKUP_HANDOFF_DESCRIPTION,
    "escalate_to_human": ESCALATE_TO_HUMAN_DESCRIPTION,
}


def get_customer(
    backend: SupportBackend,
    session: SessionState,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    found = find_customers(backend, arguments)
    query = {
        "email": (arguments.get("email") or "").strip() or None,
        "customer_id": (arguments.get("customer_id") or "").strip() or None,
    }
    if isinstance(found, dict):
        return found

    matches = [public_customer(row) for row in found]
    verified = len(matches) == 1 and matches[0]["account_status"] == "active"
    if not matches:
        message = "No customer matched the query."
    elif verified:
        message = f"Verified {matches[0]['customer_id']}."
    elif len(matches) == 1:
        message = (
            f"Found {matches[0]['customer_id']} but account_status is "
            f"{matches[0]['account_status']}. Not verified for refunds."
        )
    else:
        message = (
            f"{len(matches)} customers matched. Ask for another identifier. "
            "Do not choose one."
        )
    body = ok(
        "get_customer",
        message,
        {"matches": matches, "verified": verified},
        query,
    )
    session.remember_customer(body["data"])
    return body


def lookup_order(
    backend: SupportBackend,
    session: SessionState,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    order_id = (arguments.get("order_id") or "").strip()
    customer_id = (arguments.get("customer_id") or "").strip()
    blocked = lookup_precondition(session, arguments)
    if blocked is not None:
        return blocked
    query = {
        "order_id": order_id or None,
        "customer_id": customer_id or None,
    }
    if not order_id and not customer_id:
        return fail(
            "lookup_order",
            "validation",
            False,
            "Provide order_id or customer_id.",
            query,
        )
    orders = backend.orders_for(
        order_id=order_id or None,
        customer_id=customer_id or None,
    )
    if not orders:
        return ok("lookup_order", "No orders matched the query.", {"orders": []}, query)
    if any(order.get("customer_id") != session.verified_customer_id for order in orders):
        return fail(
            "lookup_order",
            "permission",
            False,
            "That order belongs to another customer. Do not use it.",
            query,
        )
    return ok(
        "lookup_order",
        f"Found {len(orders)} order(s).",
        {"orders": orders},
        query,
    )


def process_refund(
    backend: SupportBackend,
    session: SessionState,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    blocked = refund_precondition(session, arguments)
    if blocked is not None:
        if "automatic limit" in blocked["message"]:
            saved = record_cap_handoff(backend, session, arguments)
            if saved and saved.get("already_open"):
                blocked = dict(blocked)
                blocked["message"] = ALREADY_OPEN_MESSAGE
                blocked["partialResults"] = {
                    "order_id": saved.get("order_id"),
                    "handoff_id": saved.get("handoff_id"),
                }
        return blocked

    order_id = (arguments.get("order_id") or "").strip()
    reason = (arguments.get("reason") or "").strip()
    amount = parse_amount(arguments.get("amount"))
    query = {
        "customer_id": arguments.get("customer_id"),
        "order_id": order_id or None,
        "amount": arguments.get("amount"),
        "reason": reason or None,
    }
    if not order_id or not reason or amount is None or amount <= 0:
        return fail(
            "process_refund",
            "validation",
            False,
            "Provide order_id, a positive amount, and reason.",
            query,
        )

    try:
        result = backend.issue_refund(
            customer_id=session.verified_customer_id or "",
            order_id=order_id,
            amount=amount.quantize(Decimal("0.01")),
            reason=reason,
        )
    except TransientStoreError:
        return fail(
            "process_refund",
            "transient",
            True,
            "Refund write timed out. Retry the same request.",
            query,
        )
    if result["status"] == "not_found":
        return fail(
            "process_refund",
            "business",
            False,
            "No refundable order matched that id for the verified customer.",
            query,
        )
    if result["status"] == "already_refunded":
        return fail(
            "process_refund",
            "business",
            False,
            f"{order_id} is already refunded.",
            query,
            partial_results={"order_id": order_id, "total": str(result["total"])},
        )
    if result["status"] == "window_closed":
        return fail(
            "process_refund",
            "business",
            False,
            f"The return window for {order_id} is closed.",
            query,
            partial_results={
                "order_id": order_id,
                "total": str(result["total"]),
                "currency": result["currency"],
            },
        )
    if result["status"] == "currency":
        return fail(
            "process_refund",
            "business",
            False,
            f"Order currency is {result['currency']}. Automatic refunds are USD only.",
            query,
            partial_results={"order_id": order_id, "total": str(result["total"])},
        )
    if result["status"] == "exceeds_total":
        return fail(
            "process_refund",
            "business",
            False,
            f"Amount exceeds the order total of {result['total']} {result['currency']}.",
            query,
            partial_results={"order_id": order_id, "total": str(result["total"])},
        )
    refund = {
        "refund_id": result["refund_id"],
        "order_id": result["order_id"],
        "customer_id": result["customer_id"],
        "amount": str(result["amount"]),
        "currency": result["currency"],
        "reason": reason,
    }
    body = ok("process_refund", f"Refunded {refund['amount']} USD on {order_id}.", refund, query)
    session.remember_refund(body["data"])
    return body


def _remember_handoff(session: SessionState, handoff: dict[str, Any]) -> dict[str, Any]:
    order_id = handoff.get("order_id")
    for existing in session.handoffs:
        if order_id and existing.get("order_id") == order_id:
            existing.update(handoff)
            return existing
    session.handoffs.append(handoff)
    return handoff


def save_handoff(
    backend: SupportBackend,
    session: SessionState,
    handoff: dict[str, Any],
) -> dict[str, Any]:
    """Un ticket por pedido. Una corrida nueva no abre otro para la misma compra."""
    existing = backend.handoff_for_order(handoff.get("order_id"))
    if existing is not None:
        remembered = dict(existing)
        remembered["already_open"] = True
        return _remember_handoff(session, remembered)
    for open_ticket in session.handoffs:
        if handoff.get("order_id") and open_ticket.get("order_id") == handoff.get("order_id"):
            open_ticket["already_open"] = True
            return open_ticket
    stored = _remember_handoff(session, dict(handoff))
    backend.record_handoff(stored)
    return stored


def record_cap_handoff(
    backend: SupportBackend,
    session: SessionState,
    arguments: dict[str, Any],
) -> dict[str, Any] | None:
    amount = parse_amount(arguments.get("amount"))
    if amount is None or amount <= AUTO_REFUND_LIMIT:
        return None
    shown = str(amount.quantize(Decimal("0.01")))
    order_id = arguments.get("order_id")
    return save_handoff(
        backend,
        session,
        {
            "customer_id": arguments.get("customer_id") or session.verified_customer_id,
            "order_id": order_id,
            "refund_amount": shown,
            "root_cause": "refund exceeds the 500 USD automatic limit",
            "reason": f"Refund of {shown} USD exceeds the automatic limit.",
            "recommended_action": (
                f"A person reviews the refund of {shown} USD for order {order_id}."
            ),
            "caseFacts": session.snapshot(),
        },
    )


def escalate_to_human(
    backend: SupportBackend,
    session: SessionState,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    reason = (arguments.get("reason") or "").strip()
    recommended = (arguments.get("recommended_action") or "").strip()
    query = {
        "customer_id": arguments.get("customer_id"),
        "order_id": arguments.get("order_id"),
        "refund_amount": arguments.get("refund_amount"),
        "reason": reason or None,
    }
    if not reason or not recommended:
        return fail(
            "escalate_to_human",
            "validation",
            False,
            "Provide reason and recommended_action. The human has no transcript.",
            query,
        )
    handoff = save_handoff(
        backend,
        session,
        {
            "customer_id": arguments.get("customer_id") or session.verified_customer_id,
            "order_id": arguments.get("order_id"),
            "refund_amount": (
                None
                if arguments.get("refund_amount") is None
                else str(arguments.get("refund_amount"))
            ),
            "root_cause": arguments.get("root_cause"),
            "reason": reason,
            "recommended_action": recommended,
            "caseFacts": session.snapshot(),
        },
    )
    if handoff.get("already_open"):
        return ok("escalate_to_human", ALREADY_OPEN_MESSAGE, handoff, query)
    return ok(
        "escalate_to_human",
        "Handoff recorded. The human does not see the transcript.",
        handoff,
        query,
    )


def lookup_handoff(
    backend: SupportBackend,
    session: SessionState,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    order_id = (arguments.get("order_id") or "").strip()
    query = {"order_id": order_id or None}
    if not order_id:
        return fail(
            "lookup_handoff",
            "validation",
            False,
            "Provide order_id.",
            query,
        )
    row = backend.handoff_for_order(order_id)
    if row is None:
        return ok(
            "lookup_handoff",
            "No handoff ticket exists for this order.",
            {"handoffs": []},
            query,
        )
    remembered = dict(row)
    remembered["already_open"] = True
    _remember_handoff(session, remembered)
    return ok(
        "lookup_handoff",
        ALREADY_OPEN_MESSAGE,
        {"handoffs": [remembered], "already_open": True},
        query,
    )


DISPATCH = {
    "get_customer": get_customer,
    "lookup_order": lookup_order,
    "process_refund": process_refund,
    "lookup_handoff": lookup_handoff,
    "escalate_to_human": escalate_to_human,
}


def dispatch_tool(
    backend: SupportBackend,
    session: SessionState,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    name = short_tool_name(tool_name)
    handler = DISPATCH.get(name)
    if handler is None:
        return fail(
            name,
            "validation",
            False,
            f"Unknown tool {tool_name}.",
            arguments,
        )
    return handler(backend, session, arguments)

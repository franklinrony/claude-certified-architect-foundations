"""Hooks del Agent SDK. Niegan o reescriben. No llaman al modelo.

El bucle local usa las mismas funciones sync. ``sdk_runner`` las envuelve
con la firma async que espera el SDK.
"""

from __future__ import annotations

import json
from typing import Any

from support_agent.errors import as_mcp, fail
from support_agent.gates import lookup_precondition, refund_precondition, short_tool_name
from support_agent.normalize import normalize_order
from support_agent.session import SessionState


def deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def pre_tool_decision(
    session: SessionState,
    tool_name: str,
    tool_input: dict[str, Any] | None,
    backend: Any = None,
) -> dict[str, Any]:
    name = short_tool_name(tool_name)
    payload = tool_input or {}
    if name == "lookup_order":
        blocked = lookup_precondition(session, payload)
        if blocked is not None:
            return deny(blocked["message"])
        return {}
    if name != "process_refund":
        return {}
    blocked = refund_precondition(session, payload)
    if blocked is None:
        return {}
    if backend is not None and "automatic limit" in blocked["message"]:
        from support_agent.tools import ALREADY_OPEN_MESSAGE, record_cap_handoff

        saved = record_cap_handoff(backend, session, payload)
        if saved and saved.get("already_open"):
            return deny(ALREADY_OPEN_MESSAGE)
    return deny(blocked["message"])


def post_tool_decision(
    session: SessionState,
    tool_name: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Devuelve el cuerpo que debe ver el modelo, con case facts al final."""
    name = short_tool_name(tool_name)
    updated = dict(body)
    data = dict(updated.get("data") or {})

    if updated.get("ok") and name == "lookup_order":
        orders = [normalize_order(order) for order in data.get("orders") or []]
        data["orders"] = orders
        session.remember_orders(orders)
        updated["data"] = data

    updated["caseFacts"] = session.snapshot()
    return updated


def hook_denial_result(tool_name: str, reason: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Resultado de tool cuando el hook negó la llamada y el tool no corrió."""
    category = (
        "business"
        if "automatic limit" in reason or "already exists" in reason
        else "permission"
    )
    return fail(
        short_tool_name(tool_name),
        category,
        False,
        reason,
        tool_input,
    )


def make_pre_tool_hook(session: SessionState, backend: Any = None):
    async def hook(input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict[str, Any]:
        del tool_use_id, context
        return pre_tool_decision(
            session,
            input_data.get("tool_name", ""),
            input_data.get("tool_input") or {},
            backend,
        )

    return hook


def make_post_tool_hook(session: SessionState):
    async def hook(input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict[str, Any]:
        del tool_use_id, context
        response = input_data.get("tool_response")
        body = _body_from_tool_response(response)
        if body is None:
            return {}
        updated = post_tool_decision(session, input_data.get("tool_name", ""), body)
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "updatedToolOutput": as_mcp(updated),
            }
        }

    return hook


def _body_from_tool_response(response: Any) -> dict[str, Any] | None:
    if isinstance(response, dict) and "ok" in response:
        return response
    if not isinstance(response, dict):
        return None
    content = response.get("content")
    if not isinstance(content, list) or not content:
        return None
    text = content[0].get("text") if isinstance(content[0], dict) else None
    if not isinstance(text, str):
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None

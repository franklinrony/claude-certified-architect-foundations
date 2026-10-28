"""Cuerpos de tool que el modelo puede usar para decidir el siguiente paso.

Un resultado vacío y válido no es un error. Un fallo no se disfraza de éxito.
"""

from __future__ import annotations

import json
from typing import Any


def ok(
    tool: str,
    message: str,
    data: dict[str, Any],
    attempted_query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "ok": True,
        "isError": False,
        "tool": tool,
        "message": message,
        "data": data,
    }
    if attempted_query is not None:
        body["attemptedQuery"] = attempted_query
    return body


def fail(
    tool: str,
    category: str,
    retryable: bool,
    message: str,
    attempted_query: dict[str, Any] | None = None,
    partial_results: Any = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "isError": True,
        "tool": tool,
        "errorCategory": category,
        "isRetryable": retryable,
        "message": message,
        "partialResults": partial_results,
        "attemptedQuery": attempted_query or {},
        "data": data,
    }


def as_mcp(body: dict[str, Any]) -> dict[str, Any]:
    """Forma que devuelve un tool del Agent SDK. ``is_error`` es el flag MCP."""
    result: dict[str, Any] = {
        "content": [{"type": "text", "text": json.dumps(body, ensure_ascii=False)}]
    }
    if body.get("isError"):
        result["is_error"] = True
    return result

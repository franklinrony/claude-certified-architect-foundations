"""Único módulo que importa el Claude Agent SDK y puede gastar API.

El resto del escenario se prueba con pytest, sin clave y sin red.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from support_agent.backend import SupportBackend
from support_agent.db import load_local_env
from support_agent.hooks import make_post_tool_hook, make_pre_tool_hook
from support_agent.loop import DEFENSIVE_TURN_CAP
from support_agent.prompt import SYSTEM_PROMPT
from support_agent.session import SessionState
from support_agent.tools import DESCRIPTIONS, TOOL_NAMES, dispatch_tool


SERVER_KEY = "support"
DEFAULT_MAX_OUTPUT_TOKENS = 4096
BLOCKED_BUILTINS = [
    "Read",
    "Write",
    "Edit",
    "Bash",
    "Glob",
    "Grep",
    "WebSearch",
    "WebFetch",
    "WebBrowser",
    "NotebookEdit",
    "Agent",
    "Task",
    "Skill",
    "TodoWrite",
]


def _load_sdk():
    try:
        import claude_agent_sdk
    except ImportError as exc:
        raise SystemExit(
            "Falta claude-agent-sdk. Instálalo solo para una corrida real: "
            "python -m pip install claude-agent-sdk"
        ) from exc
    return claude_agent_sdk


def build_sdk_tools(sdk: Any, backend: SupportBackend, session: SessionState) -> list[Any]:
    """Registra las mismas funciones locales como tools MCP in-process."""
    tool = sdk.tool
    schemas = {
        "get_customer": {
            "type": "object",
            "properties": {
                "email": {"type": "string"},
                "customer_id": {"type": "string"},
            },
        },
        "lookup_handoff": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
        "lookup_order": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "customer_id": {"type": "string"},
            },
        },
        "process_refund": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "order_id": {"type": "string"},
                "amount": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["customer_id", "order_id", "amount", "reason"],
        },
        "escalate_to_human": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "order_id": {"type": "string"},
                "refund_amount": {"type": "string"},
                "root_cause": {"type": "string"},
                "reason": {"type": "string"},
                "recommended_action": {"type": "string"},
            },
            "required": ["reason", "recommended_action"],
        },
    }
    registered = []
    for name in TOOL_NAMES:
        registered.append(_bind_tool(tool, name, schemas[name], backend, session))
    return registered


def _bind_tool(tool, name: str, schema: dict[str, Any], backend: SupportBackend, session: SessionState):
    from support_agent.errors import as_mcp

    @tool(name, DESCRIPTIONS[name], schema)
    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        return as_mcp(dispatch_tool(backend, session, name, args))

    handler.__name__ = name
    return handler


def max_output_tokens() -> int:
    """Tope de salida de cada respuesta. El SDK no tiene max_tokens en las opciones."""
    raw = os.environ.get("CLAUDE_MAX_OUTPUT_TOKENS", "").strip()
    if not raw:
        return DEFAULT_MAX_OUTPUT_TOKENS
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit("CLAUDE_MAX_OUTPUT_TOKENS debe ser un entero.") from exc
    if value < 1:
        raise SystemExit("CLAUDE_MAX_OUTPUT_TOKENS debe ser mayor que 0.")
    return value


def _token(data: dict[str, Any], *keys: str) -> int:
    for key in keys:
        if key not in data or data[key] is None:
            continue
        try:
            return int(data[key])
        except (TypeError, ValueError):
            return 0
    return 0


def usage_totals(usage: dict[str, Any] | None, model_usage: dict[str, Any] | None) -> dict[str, int]:
    """model_usage suma todo el árbol. usage del resultado deja fuera llamadas anidadas."""
    totals = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    if model_usage:
        for entry in model_usage.values():
            data = entry if isinstance(entry, dict) else {}
            totals["input"] += _token(data, "inputTokens", "input_tokens")
            totals["output"] += _token(data, "outputTokens", "output_tokens")
            totals["cache_read"] += _token(data, "cacheReadInputTokens", "cache_read_input_tokens")
            totals["cache_write"] += _token(data, "cacheCreationInputTokens", "cache_creation_input_tokens")
        return totals
    data = usage or {}
    return {
        "input": _token(data, "input_tokens", "inputTokens"),
        "output": _token(data, "output_tokens", "outputTokens"),
        "cache_read": _token(data, "cache_read_input_tokens", "cacheReadInputTokens"),
        "cache_write": _token(data, "cache_creation_input_tokens", "cacheCreationInputTokens"),
    }


_COLORS = {
    "cliente": "36",
    "agente": "32",
    "decidio": "34",
    "tool": "33",
    "handoff": "35",
    "error": "31",
    "meta": "90",
}
_TOOL_KEYS = (
    "email",
    "customer_id",
    "order_id",
    "amount",
    "refund_amount",
    "reason",
    "root_cause",
    "recommended_action",
)


def enable_console_color() -> None:
    if os.name != "nt":
        return
    import ctypes

    handle = ctypes.windll.kernel32.GetStdHandle(-11)
    mode = ctypes.c_uint()
    if ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        ctypes.windll.kernel32.SetConsoleMode(handle, mode.value | 0x0004)


def paint(role: str, text: str) -> str:
    code = _COLORS.get(role, "0")
    return f"\033[{code}m{text}\033[0m"


def _clip(text: str, limit: int = 180) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    cut = compact[:limit].rsplit(" ", 1)[0]
    return (cut or compact[:limit]) + "…"


def _tool_line(name: str, raw_input: Any) -> str:
    data = raw_input if isinstance(raw_input, dict) else {}
    parts: list[str] = []
    for key in _TOOL_KEYS:
        value = data.get(key)
        if value in (None, ""):
            continue
        shown = _clip(str(value), 80)
        parts.append(f"{key}={shown}")
    short = str(name).split("__")[-1]
    detail = "  ".join(parts)
    return f"{short}  {detail}".rstrip()


def format_usage(
    usage: dict[str, Any] | None,
    model_usage: dict[str, Any] | None,
    max_output: int,
    cost: float | None,
) -> str:
    totals = usage_totals(usage, model_usage)
    lines = [
        "Tokens",
        f"  entrada: {totals['input']}",
        f"  salida: {totals['output']}",
        f"  cache lectura: {totals['cache_read']}",
        f"  cache escritura: {totals['cache_write']}",
        f"  tope de salida por turno: {max_output}",
        f"  tope de turnos: {DEFENSIVE_TURN_CAP}",
    ]
    if cost is not None:
        lines.append(f"  costo USD: {cost:.6f}")
    return "\n".join(lines)


def trace_events(message: Any) -> list[tuple[str, str]]:
    kind = type(message).__name__
    events: list[tuple[str, str]] = []
    if kind == "AssistantMessage":
        for block in getattr(message, "content", []) or []:
            block_kind = type(block).__name__
            if block_kind == "TextBlock":
                text = str(getattr(block, "text", "")).strip()
                if text:
                    events.append(("agente", text))
            elif block_kind == "ThinkingBlock":
                thought = _clip(str(getattr(block, "thinking", "")))
                if thought:
                    events.append(("decidio", f"decidió: {thought}"))
            elif block_kind == "ToolUseBlock":
                events.append(("tool", _tool_line(getattr(block, "name", ""), getattr(block, "input", None))))
        return events
    if kind == "UserMessage":
        content = getattr(message, "content", None)
        blocks = content if isinstance(content, list) else []
        for block in blocks:
            if type(block).__name__ != "ToolResultBlock":
                continue
            content = getattr(block, "content", None)
            if isinstance(content, list):
                content = " ".join(
                    str(part.get("text", "")) for part in content if isinstance(part, dict)
                )
            text = _clip(str(content or ""))
            if not text:
                continue
            role = "error" if getattr(block, "is_error", False) else "tool"
            events.append((role, f"resultado: {text}"))
        return events
    if kind == "ResultMessage" and getattr(message, "is_error", False):
        errors = getattr(message, "errors", None) or [getattr(message, "subtype", "error")]
        events.append(("error", "error: " + "; ".join(str(item) for item in errors)))
    return events


def format_stream_message(message: Any) -> str | None:
    lines = [text for _, text in trace_events(message)]
    return "\n".join(lines) or None


def format_handoffs(
    handoffs: list[dict[str, Any]],
    refunds: list[dict[str, Any]] | None = None,
) -> str:
    if not handoffs and refunds:
        return "Handoff: no hizo falta. El reembolso quedó en la base."
    if not handoffs:
        return (
            "Handoff: no se grabó ninguno. "
            "Si un reembolso se bloquea por el tope, hace falta la tool escalate_to_human."
        )
    if all(item.get("already_open") for item in handoffs):
        lines = [
            "Handoff: el ticket de este pedido ya existe. No se creó otro. "
            "El cliente puede esperar o preguntar a soporte."
        ]
    else:
        lines = [
            "Handoff grabado en escenario_01.handoffs. No hay una persona del otro lado: queda la fila."
        ]
    for item in handoffs:
        lines.append(
            "  "
            f"orden {item.get('order_id')}  "
            f"monto {item.get('refund_amount')}  "
            f"causa {item.get('root_cause') or item.get('reason')}"
        )
        lines.append(f"  acción {item.get('recommended_action')}")
    return "\n".join(lines)


def build_options(sdk: Any, backend: SupportBackend, session: SessionState, max_output: int) -> Any:
    server = sdk.create_sdk_mcp_server(
        name=SERVER_KEY,
        version="0.1.0",
        tools=build_sdk_tools(sdk, backend, session),
    )
    # allowed_tools auto-aprueba. No esconde el resto. Por eso los built-in van en disallowed_tools.
    return sdk.ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        model=os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5"),
        max_turns=DEFENSIVE_TURN_CAP,
        env={"CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(max_output)},
        mcp_servers={SERVER_KEY: server},
        allowed_tools=[f"mcp__{SERVER_KEY}__{name}" for name in TOOL_NAMES],
        disallowed_tools=BLOCKED_BUILTINS,
        permission_mode="dontAsk",
        hooks={
            "PreToolUse": [
                sdk.HookMatcher(
                    matcher=matcher,
                    hooks=[make_pre_tool_hook(session, backend)],
                )
                for matcher in (
                    "lookup_order",
                    f"mcp__{SERVER_KEY}__lookup_order",
                    "process_refund",
                    f"mcp__{SERVER_KEY}__process_refund",
                )
            ],
            "PostToolUse": [sdk.HookMatcher(hooks=[make_post_tool_hook(session)])],
        },
    )


def run(prompt: str, chat: bool = False) -> None:
    load_local_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "Falta ANTHROPIC_API_KEY en .env. El core se estudia con pytest, sin esta variable."
        )
    sdk = _load_sdk()
    output_cap = max_output_tokens()
    backend = SupportBackend.connect()
    session = SessionState()
    options = build_options(sdk, backend, session, output_cap)

    async def _main() -> None:
        enable_console_color()

        async def one_turn(client: Any, text: str) -> None:
            print(paint("cliente", "Cliente\n" + text), flush=True)
            await client.query(text)
            async for message in client.receive_response():
                for role, line in trace_events(message):
                    print(paint(role, line), flush=True)
                if type(message).__name__ == "ResultMessage":
                    print(
                        paint(
                            "meta",
                            format_usage(
                                message.usage,
                                getattr(message, "model_usage", None),
                                output_cap,
                                message.total_cost_usd,
                            ),
                        ),
                        flush=True,
                    )

        async with sdk.ClaudeSDKClient(options=options) as client:
            await one_turn(client, prompt)
            if chat:
                print(
                    paint(
                        "meta",
                        "Misma sesión. Escribe otro mensaje. Una línea vacía cierra.",
                    ),
                    flush=True,
                )
                while True:
                    try:
                        line = input()
                    except EOFError:
                        break
                    if not line.strip():
                        break
                    await one_turn(client, line.strip())
        print(paint("handoff", format_handoffs(session.handoffs, session.refunds)), flush=True)

    try:
        asyncio.run(_main())
    finally:
        backend.close()


DEFAULT_PROMPT = "Quiero devolver el pedido ord_10. Mi correo es ana@example.test."


def customer_prompt(argv: list[str]) -> tuple[str, bool]:
    chat = "--chat" in argv[1:]
    text = " ".join(arg for arg in argv[1:] if arg != "--chat").strip()
    return text or DEFAULT_PROMPT, chat


def main() -> None:
    prompt, chat = customer_prompt(sys.argv)
    run(prompt, chat)


if __name__ == "__main__":
    main()

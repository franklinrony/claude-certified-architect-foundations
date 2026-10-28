"""Bucle agéntico explicito. Para cuando stop_reason es end_turn.

El tope de iteraciones es un riel de seguridad. No es la condición de parada.
Un modelo falso implementa el mismo contrato que usaría la API, así los tests
no llaman a Claude.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from support_agent.backend import SupportBackend
from support_agent.hooks import hook_denial_result, post_tool_decision, pre_tool_decision
from support_agent.session import SessionState
from support_agent.tools import TOOL_NAMES, dispatch_tool


DEFENSIVE_TURN_CAP = 8


class SafetyCapExceeded(RuntimeError):
    """El modelo no devolvió end_turn antes del riel defensivo."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelTurn:
    stop_reason: str
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass
class LoopResult:
    stop_reason: str
    text: str
    messages: list[dict[str, Any]]
    iterations: int
    case_facts: dict[str, Any]
    tools_executed: list[str] = field(default_factory=list)


class ModelClient(Protocol):
    def complete(self, messages: list[dict[str, Any]], tool_names: list[str]) -> ModelTurn:
        """Un turno. stop_reason es tool_use o end_turn."""


def _for_model(messages: list[dict[str, Any]], state: SessionState) -> list[dict[str, Any]]:
    """Hechos del caso al inicio de cada turno. No se resumen con el historial."""
    return [
        {"role": "user", "type": "case_facts", "content": state.snapshot()},
        *messages,
    ]


def run_agentic_loop(
    client: ModelClient,
    user_message: str,
    backend: SupportBackend,
    session: SessionState | None = None,
    max_iterations: int = DEFENSIVE_TURN_CAP,
    prior_messages: list[dict[str, Any]] | None = None,
) -> LoopResult:
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1")
    state = session or SessionState()
    messages: list[dict[str, Any]] = list(prior_messages or [])
    messages.append({"role": "user", "content": user_message})
    tool_names = list(TOOL_NAMES)
    executed: list[str] = []

    for iteration in range(1, max_iterations + 1):
        turn = client.complete(_for_model(messages, state), tool_names)
        messages.append(
            {
                "role": "assistant",
                "stop_reason": turn.stop_reason,
                "content": turn.text,
                "tool_calls": [
                    {"id": call.id, "name": call.name, "arguments": call.arguments}
                    for call in turn.tool_calls
                ],
            }
        )
        if turn.stop_reason == "end_turn":
            return LoopResult(
                stop_reason="end_turn",
                text=turn.text,
                messages=messages,
                iterations=iteration,
                case_facts=state.snapshot(),
                tools_executed=executed,
            )
        if turn.stop_reason != "tool_use":
            raise ValueError(
                f"Unexpected stop_reason {turn.stop_reason!r}. "
                "Continue only on tool_use and stop only on end_turn."
            )
        if not turn.tool_calls:
            raise ValueError("stop_reason tool_use requires at least one tool call")

        for call in turn.tool_calls:
            decision = pre_tool_decision(state, call.name, call.arguments, backend)
            if decision:
                reason = decision["hookSpecificOutput"]["permissionDecisionReason"]
                body = hook_denial_result(call.name, reason, call.arguments)
            else:
                body = dispatch_tool(backend, state, call.name, call.arguments)
                executed.append(call.name)
            body = post_tool_decision(state, call.name, body)
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": call.id,
                            "is_error": bool(body.get("isError")),
                            "content": body,
                        }
                    ],
                }
            )

    raise SafetyCapExceeded(
        f"Stopped after {max_iterations} iterations without end_turn. "
        "The cap is a safety rail, not the completion signal."
    )

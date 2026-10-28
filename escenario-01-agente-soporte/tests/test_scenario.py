"""El escenario 1 se demuestra sin Claude API."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from support_agent.backend import SupportBackend
from support_agent.db import TransientStoreError
from support_agent.errors import as_mcp, ok
from support_agent.hooks import make_post_tool_hook, make_pre_tool_hook
from support_agent.loop import (
    DEFENSIVE_TURN_CAP,
    LoopResult,
    ModelTurn,
    SafetyCapExceeded,
    ToolCall,
    run_agentic_loop,
)
from support_agent.normalize import normalize_order
from support_agent.session import SessionState
from support_agent.tools import (
    DESCRIPTIONS,
    TOOL_NAMES,
    escalate_to_human,
    get_customer,
    lookup_handoff,
    lookup_order,
    process_refund,
)
import support_agent.sdk_runner as sdk_runner


class ScriptedModel:
    def __init__(self, turns: list[ModelTurn]) -> None:
        self.turns = list(turns)
        self.seen: list[tuple[list, list[str]]] = []

    def complete(self, messages, tool_names):
        self.seen.append((list(messages), list(tool_names)))
        if not self.turns:
            raise AssertionError("the scripted model ran out of turns")
        return self.turns.pop(0)


@pytest.fixture
def backend():
    db = SupportBackend.connect()
    db.conn.execute("BEGIN")
    try:
        yield db
    finally:
        db.conn.rollback()
        db.close()


def _session() -> SessionState:
    return SessionState()


def _refund_call(call_id: str, amount: str, order_id: str) -> ToolCall:
    return ToolCall(
        call_id,
        "process_refund",
        {
            "customer_id": "cus_100",
            "order_id": order_id,
            "amount": amount,
            "reason": "damaged",
        },
    )


def test_descriptions_separate_the_tools() -> None:
    assert set(DESCRIPTIONS) == set(TOOL_NAMES)
    texts = list(DESCRIPTIONS.values())
    assert len(set(texts)) == len(TOOL_NAMES)
    assert "does not look up orders" in DESCRIPTIONS["get_customer"].lower()
    assert "does not verify identity" in DESCRIPTIONS["lookup_order"].lower()
    assert "does not search for the customer" in DESCRIPTIONS["process_refund"].lower()
    assert "does not create a ticket" in DESCRIPTIONS["lookup_handoff"].lower()
    assert "tell the customer to wait" in DESCRIPTIONS["lookup_handoff"].lower()
    assert "sounds upset" in DESCRIPTIONS["escalate_to_human"].lower()


def test_one_ticket_per_order(backend: SupportBackend) -> None:
    order_id = "ord_once"
    before = backend.handoff_count()
    session = _session()

    empty = lookup_handoff(backend, session, {"order_id": order_id})
    assert empty["ok"] is True
    assert empty["data"]["handoffs"] == []
    assert session.handoffs == []
    assert backend.handoff_count() == before

    missing = lookup_handoff(backend, session, {})
    assert missing["errorCategory"] == "validation"
    assert missing["isRetryable"] is False

    payload = {
        "customer_id": "cus_100",
        "order_id": order_id,
        "refund_amount": "780.00",
        "root_cause": "refund exceeds the 500 USD automatic limit",
        "reason": "over the automatic limit",
        "recommended_action": "a person reviews 780.00 USD",
    }
    opened = escalate_to_human(backend, session, payload)
    assert opened["ok"] is True
    assert opened["data"].get("already_open") is not True
    assert backend.handoff_count() == before + 1

    other = _session()
    found = lookup_handoff(backend, other, {"order_id": order_id})
    assert found["ok"] is True
    assert "already exists" in found["message"]
    assert "wait" in found["message"]
    assert found["data"]["already_open"] is True
    assert other.handoffs[0]["order_id"] == order_id
    assert backend.handoff_count() == before + 1

    again = escalate_to_human(backend, _session(), dict(payload, reason="customer asked again"))
    assert again["ok"] is True
    assert "already exists" in again["message"]
    assert again["data"]["already_open"] is True
    assert backend.handoff_count() == before + 1


def test_error_classes_and_empty_success(backend: SupportBackend) -> None:
    session = _session()

    missing = get_customer(backend, session, {"email": "nobody@example.test"})
    assert missing["ok"] is True
    assert missing["isError"] is False
    assert missing["data"]["matches"] == []
    assert "errorCategory" not in missing

    ambiguous = get_customer(backend, session, {"email": "shared@example.test"})
    assert ambiguous["data"]["verified"] is False
    assert len(ambiguous["data"]["matches"]) == 2
    assert session.verified_customer_id is None

    blocked_lookup = lookup_order(backend, session, {"order_id": "ord_missing"})
    assert blocked_lookup["errorCategory"] == "permission"
    assert blocked_lookup["isRetryable"] is False
    assert "before lookup_order" in blocked_lookup["message"]

    get_customer(backend, session, {"customer_id": "cus_100"})
    empty_order = lookup_order(backend, session, {"order_id": "ord_missing"})
    assert empty_order["ok"] is True
    assert empty_order["data"]["orders"] == []
    foreign = lookup_order(backend, session, {"order_id": "ord_20"})
    assert foreign["errorCategory"] == "permission"
    assert "another customer" in foreign["message"]
    assert "orders" not in (foreign.get("data") or {})

    invalid = lookup_order(backend, session, {})
    assert invalid["errorCategory"] == "validation"
    assert invalid["isRetryable"] is False


def test_identity_and_refund_cap_hold_without_a_prompt(backend: SupportBackend) -> None:
    session = _session()

    blocked = process_refund(
        backend,
        session,
        {
            "customer_id": "cus_100",
            "order_id": "ord_10",
            "amount": "42.50",
            "reason": "damaged",
        },
    )
    assert blocked["errorCategory"] == "permission"
    assert blocked["isRetryable"] is False
    assert "ref_ord_10" not in backend.refund_ids()

    get_customer(backend, session, {"customer_id": "cus_300"})
    restricted = process_refund(
        backend,
        session,
        {
            "customer_id": "cus_300",
            "order_id": "ord_10",
            "amount": "42.50",
            "reason": "damaged",
        },
    )
    assert restricted["errorCategory"] == "permission"
    assert "ref_ord_10" not in backend.refund_ids()

    get_customer(backend, session, {"customer_id": "cus_100"})
    too_big = process_refund(
        backend,
        session,
        {
            "customer_id": "cus_100",
            "order_id": "ord_11",
            "amount": "780.00",
            "reason": "too expensive",
        },
    )
    assert too_big["errorCategory"] == "business"
    assert too_big["isRetryable"] is False
    assert (
        "escalate_to_human" in too_big["message"]
        or "already exists" in too_big["message"]
    )
    assert "ref_ord_11" not in backend.refund_ids()

    closed = process_refund(
        backend,
        session,
        {
            "customer_id": "cus_100",
            "order_id": "ord_12",
            "amount": "15.00",
            "reason": "late",
        },
    )
    assert closed["errorCategory"] == "business"
    assert closed["partialResults"]["total"] == "15.00"
    assert "ref_ord_12" not in backend.refund_ids()

    done = process_refund(
        backend,
        session,
        {
            "customer_id": "cus_100",
            "order_id": "ord_10",
            "amount": "42.50",
            "reason": "damaged",
        },
    )
    assert done["ok"] is True
    assert done["data"]["amount"] == "42.50"
    assert done["data"]["refund_id"] == "ref_ord_10"

    again = process_refund(
        backend,
        session,
        {
            "customer_id": "cus_100",
            "order_id": "ord_10",
            "amount": "42.50",
            "reason": "damaged",
        },
    )
    assert again["message"].endswith("already refunded.")
    assert backend.refund_ids().count("ref_ord_10") == 1

    get_customer(backend, session, {"customer_id": "cus_200"})
    prior = process_refund(
        backend,
        session,
        {
            "customer_id": "cus_200",
            "order_id": "ord_30",
            "amount": "18.00",
            "reason": "again",
        },
    )
    assert prior["message"].endswith("already refunded.")

    get_customer(backend, session, {"customer_id": "cus_500"})
    euro = process_refund(
        backend,
        session,
        {
            "customer_id": "cus_500",
            "order_id": "ord_20",
            "amount": "20.00",
            "reason": "notebook",
        },
    )
    assert euro["errorCategory"] == "business"
    assert "EUR" in euro["message"]


def test_refund_stays_after_the_connection_closes() -> None:
    writer = SupportBackend.connect()
    reader = SupportBackend.connect()
    inserted = False
    try:
        assert "ref_ord_10" not in reader.refund_ids()
        result = writer.issue_refund(
            customer_id="cus_100",
            order_id="ord_10",
            amount=Decimal("42.50"),
            reason="persistencia",
        )
        assert result["status"] == "ok"
        inserted = True
        assert "ref_ord_10" in reader.refund_ids()
    finally:
        if inserted:
            writer.conn.execute(
                "DELETE FROM escenario_01.refunds WHERE refund_id = %s",
                ("ref_ord_10",),
            )
        writer.close()
        reader.close()


def test_normalize_trims_and_keeps_amounts(backend: SupportBackend) -> None:
    session = _session()
    raw = backend.order_by_id("ord_10")
    assert raw is not None
    normalized = normalize_order(raw)
    assert normalized == normalize_order(normalized)
    assert normalized["status"] == "delivered"
    assert normalized["total"] == "42.50"
    assert normalized["placed_at"] == "2026-10-01T00:00:00Z"
    legacy = backend.order_by_id("ord_11")
    assert legacy is not None
    assert isinstance(legacy["placed_at"], int)
    assert normalize_order(legacy)["placed_at"] == datetime.fromtimestamp(
        legacy["placed_at"], timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    dumped = json.dumps(normalized)
    assert "payment_token" not in dumped
    assert "shipping_address" not in dumped
    assert "warehouse" not in dumped
    assert normalized["items"] == [{"name": "Mug", "qty": 1}]

    hook = make_post_tool_hook(session)
    body = ok("lookup_order", "Found 2 order(s).", {"orders": backend.orders_for(order_id=None, customer_id="cus_100")})
    result = asyncio.run(
        hook(
            {
                "tool_name": "mcp__support__lookup_order",
                "tool_response": as_mcp(body),
            },
            None,
            None,
        )
    )
    text = result["hookSpecificOutput"]["updatedToolOutput"]["content"][0]["text"]
    parsed = json.loads(text)
    totals = [order["total"] for order in parsed["data"]["orders"]]
    assert totals == ["42.50", "780.00", "15.00"]
    assert parsed["caseFacts"]["orders"][1]["total"] == "780.00"
    assert "tok_big" not in text


def test_pre_tool_hook_blocks_the_mcp_tool_name(backend: SupportBackend) -> None:
    session = _session()
    hook = make_pre_tool_hook(session)
    denied = asyncio.run(
        hook(
            {
                "tool_name": "mcp__support__process_refund",
                "tool_input": {
                    "customer_id": "cus_100",
                    "order_id": "ord_10",
                    "amount": "42.50",
                    "reason": "damaged",
                },
            },
            None,
            None,
        )
    )
    decision = denied["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert decision["hookEventName"] == "PreToolUse"

    get_customer(backend, session, {"customer_id": "cus_100"})
    allowed = asyncio.run(
        hook(
            {
                "tool_name": "mcp__support__process_refund",
                "tool_input": {
                    "customer_id": "cus_100",
                    "order_id": "ord_10",
                    "amount": "42.50",
                    "reason": "damaged",
                },
            },
            None,
            None,
        )
    )
    assert allowed == {}

    fresh = _session()
    hook_again = make_pre_tool_hook(fresh, backend)
    still_denied = asyncio.run(
        hook_again(
            {"tool_name": "lookup_order", "tool_input": {"order_id": "ord_10"}},
            None,
            None,
        )
    )
    assert "before lookup_order" in still_denied["hookSpecificOutput"]["permissionDecisionReason"]
    get_customer(backend, fresh, {"customer_id": "cus_100"})
    allowed_lookup = asyncio.run(
        hook_again(
            {"tool_name": "lookup_order", "tool_input": {"order_id": "ord_10"}},
            None,
            None,
        )
    )
    assert allowed_lookup == {}


def test_loop_stops_on_end_turn_and_appends_tool_results(backend: SupportBackend) -> None:
    session = _session()
    model = ScriptedModel(
        [
            ModelTurn(
                "tool_use",
                "I should look them up first.",
                (
                    ToolCall("call_1", "get_customer", {"customer_id": "cus_100"}),
                    ToolCall("call_2", "lookup_order", {"customer_id": "cus_100"}),
                ),
            ),
            ModelTurn("end_turn", "Refund of 42.50 USD is available on ord_10."),
        ]
    )
    result = run_agentic_loop(model, "Where is my mug order?", backend, session)

    assert isinstance(result, LoopResult)
    assert result.stop_reason == "end_turn"
    assert result.iterations == 2
    assert result.tools_executed == ["get_customer", "lookup_order"]
    assert model.seen[1][0][0]["type"] == "case_facts"
    assert model.seen[1][0][0]["content"]["verified_customer_id"] == "cus_100"
    assert model.seen[1][0][0]["content"]["orders"]
    assert model.seen[1][0][-1]["content"][0]["type"] == "tool_result"
    assert model.seen[0][1] == list(TOOL_NAMES)
    totals = [order["total"] for order in result.case_facts["orders"]]
    assert "42.50" in totals
    assert "780.00" in totals
    assert result.case_facts["verified_customer_id"] == "cus_100"


def test_loop_does_not_stop_on_assistant_text(backend: SupportBackend) -> None:
    session = _session()
    model = ScriptedModel(
        [
            ModelTurn(
                "tool_use",
                "TASK COMPLETE",
                (ToolCall("call_1", "get_customer", {"email": "ana@example.test"}),),
            ),
            ModelTurn("end_turn", ""),
        ]
    )
    result = run_agentic_loop(model, "hi", backend, session)
    assert result.stop_reason == "end_turn"
    assert result.iterations == 2
    assert result.tools_executed == ["get_customer"]


def test_end_turn_does_not_run_a_trailing_tool_call(backend: SupportBackend) -> None:
    session = _session()
    model = ScriptedModel(
        [
            ModelTurn(
                "end_turn",
                "Nothing to do.",
                (_refund_call("call_1", "42.50", "ord_10"),),
            )
        ]
    )
    result = run_agentic_loop(model, "hi", backend, session)
    assert result.tools_executed == []
    assert "ref_ord_10" not in backend.refund_ids()


def test_hook_stops_the_refund_before_the_tool_runs(backend: SupportBackend) -> None:
    session = _session()
    model = ScriptedModel(
        [
            ModelTurn("tool_use", "", (_refund_call("call_1", "42.50", "ord_10"),)),
            ModelTurn(
                "tool_use",
                "",
                (ToolCall("call_2", "get_customer", {"customer_id": "cus_100"}),),
            ),
            ModelTurn("tool_use", "", (_refund_call("call_3", "780.00", "ord_11"),)),
            ModelTurn("end_turn", "I need a person for the 780.00 USD refund."),
        ]
    )
    ticket_existed = backend.handoff_for_order("ord_11") is not None
    before_handoffs = backend.handoff_count()
    result = run_agentic_loop(model, "refund everything", backend, session)

    assert result.tools_executed == ["get_customer"]
    assert "ref_ord_10" not in backend.refund_ids()
    assert "ref_ord_11" not in backend.refund_ids()
    first = model.seen[1][0][-1]["content"][0]["content"]
    third = model.seen[3][0][-1]["content"][0]["content"]
    assert first["errorCategory"] == "permission"
    assert third["errorCategory"] == "business"
    assert third["isRetryable"] is False
    if ticket_existed:
        assert "already exists" in third["message"]
    else:
        assert "780.00" in third["message"]
    assert len(session.handoffs) == 1
    assert session.handoffs[0]["order_id"] == "ord_11"
    assert session.handoffs[0]["refund_amount"] == "780.00"
    assert backend.handoff_count() == before_handoffs + (0 if ticket_existed else 1)

    again = _session()
    run_agentic_loop(
        ScriptedModel(
            [
                ModelTurn(
                    "tool_use",
                    "",
                    (ToolCall("call_4", "get_customer", {"customer_id": "cus_100"}),),
                ),
                ModelTurn("tool_use", "", (_refund_call("call_5", "780.00", "ord_11"),)),
                ModelTurn("end_turn", "The ticket is already open."),
            ]
        ),
        "refund ord_11 again",
        backend,
        again,
    )
    assert backend.handoff_count() == before_handoffs + (0 if ticket_existed else 1)
    assert again.handoffs[0]["already_open"] is True


def test_two_concerns_share_one_verified_session(backend: SupportBackend) -> None:
    session = _session()
    model = ScriptedModel(
        [
            ModelTurn(
                "tool_use",
                "Primero verifico a Ana.",
                (ToolCall("call_1", "get_customer", {"email": "ana@example.test"}),),
            ),
            ModelTurn(
                "tool_use",
                "Son dos pedidos.",
                (
                    ToolCall("call_2", "lookup_order", {"order_id": "ord_10"}),
                    ToolCall("call_3", "lookup_order", {"order_id": "ord_12"}),
                ),
            ),
            ModelTurn("tool_use", "Solo ord_10 está en ventana.", (_refund_call("call_4", "42.50", "ord_10"),)),
            ModelTurn(
                "end_turn",
                "ord_10 refunded 42.50 USD. ord_12 stays 15.00 USD because the window is closed.",
            ),
        ]
    )
    result = run_agentic_loop(
        model,
        "Devuelve ord_10 y explícame el cargo de ord_12. Soy ana@example.test.",
        backend,
        session,
    )
    pair = next(
        message
        for message in model.seen[2][0]
        if message.get("role") == "assistant" and len(message.get("tool_calls") or []) == 2
    )
    assert {call["arguments"]["order_id"] for call in pair["tool_calls"]} == {"ord_10", "ord_12"}
    assert result.stop_reason == "end_turn"
    assert result.tools_executed == ["get_customer", "lookup_order", "lookup_order", "process_refund"]
    assert "ref_ord_10" in backend.refund_ids()
    assert "ref_ord_12" not in backend.refund_ids()
    assert "42.50" in result.text and "15.00" in result.text
    assert result.case_facts["verified_customer_id"] == "cus_100"


def test_follow_up_keeps_the_same_case(backend: SupportBackend) -> None:
    session = _session()
    first = run_agentic_loop(
        ScriptedModel(
            [
                ModelTurn(
                    "tool_use",
                    "",
                    (ToolCall("call_1", "get_customer", {"email": "shared@example.test"}),),
                ),
                ModelTurn("end_turn", "Two customers match. Which customer id is yours?"),
            ]
        ),
        "My email is shared@example.test.",
        backend,
        session,
    )
    assert session.verified_customer_id is None
    second = run_agentic_loop(
        ScriptedModel(
            [
                ModelTurn(
                    "tool_use",
                    "",
                    (ToolCall("call_2", "get_customer", {"customer_id": "cus_200"}),),
                ),
                ModelTurn("end_turn", "Verified cus_200."),
            ]
        ),
        "The id is cus_200.",
        backend,
        session,
        prior_messages=first.messages,
    )
    history = json.dumps(second.messages)
    assert "shared@example.test" in history
    assert "cus_200" in history
    assert second.case_facts["verified_customer_id"] == "cus_200"
    assert second.iterations == 2


def test_eight_model_turns_are_the_rail(backend: SupportBackend) -> None:
    calls = {"n": 0}

    class AlwaysTools:
        def complete(self, messages, tool_names):
            del messages, tool_names
            calls["n"] += 1
            return ModelTurn(
                "tool_use",
                "",
                (ToolCall(f"c{calls['n']}", "get_customer", {"email": "ana@example.test"}),),
            )

    with pytest.raises(SafetyCapExceeded, match="safety rail"):
        run_agentic_loop(AlwaysTools(), "sigue", backend)
    assert calls["n"] == DEFENSIVE_TURN_CAP == 8

    finished = run_agentic_loop(
        ScriptedModel(
            [
                ModelTurn(
                    "tool_use",
                    "",
                    (ToolCall(f"ok{n}", "get_customer", {"customer_id": "cus_100"}),),
                )
                for n in range(7)
            ]
            + [ModelTurn("end_turn", "Listo en el turno 8.")]
        ),
        "confirma a Ana",
        backend,
        _session(),
    )
    assert finished.iterations == 8
    assert finished.stop_reason == "end_turn"


def test_safety_cap_is_not_a_successful_stop(backend: SupportBackend) -> None:
    session = _session()
    model = ScriptedModel(
        [
            ModelTurn(
                "tool_use",
                "",
                (ToolCall("call_1", "lookup_order", {"order_id": "ord_missing"}),),
            )
        ]
        * 3
    )
    with pytest.raises(SafetyCapExceeded, match="safety rail"):
        run_agentic_loop(model, "loop forever", backend, session, max_iterations=2)


def test_database_timeout_is_retryable(backend: SupportBackend, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_email: str) -> list[dict]:
        raise TransientStoreError("database timeout")

    monkeypatch.setattr(backend, "customers_by_email", boom)
    body = get_customer(backend, _session(), {"email": "ana@example.test"})
    assert body["errorCategory"] == "transient"
    assert body["isRetryable"] is True
    assert as_mcp(body)["is_error"] is True


def test_postgres_cancel_is_transient(backend: SupportBackend) -> None:
    backend.conn.execute("SET LOCAL statement_timeout = '30ms'")
    with pytest.raises(TransientStoreError):
        backend.fetch_all("SELECT pg_sleep(1)")


def test_each_exam_scenario_has_its_own_schema(backend: SupportBackend) -> None:
    names = [
        row["nspname"]
        for row in backend.fetch_all(
            "SELECT nspname FROM pg_namespace WHERE nspname LIKE 'escenario_%%' ORDER BY 1"
        )
    ]
    assert names == [f"escenario_0{index}" for index in range(1, 7)]
    others = backend.fetch_all(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema LIKE 'escenario_%%'
          AND table_schema <> 'escenario_01'
        """
    )
    assert others == []


def test_max_output_tokens_defaults_and_rejects_junk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_MAX_OUTPUT_TOKENS", raising=False)
    assert sdk_runner.max_output_tokens() == sdk_runner.DEFAULT_MAX_OUTPUT_TOKENS
    monkeypatch.setenv("CLAUDE_MAX_OUTPUT_TOKENS", "512")
    assert sdk_runner.max_output_tokens() == 512
    monkeypatch.setenv("CLAUDE_MAX_OUTPUT_TOKENS", "no")
    with pytest.raises(SystemExit, match="CLAUDE_MAX_OUTPUT_TOKENS"):
        sdk_runner.max_output_tokens()


def test_usage_report_sums_models_and_shows_the_cap() -> None:
    text = sdk_runner.format_usage(
        {"input_tokens": 1, "output_tokens": 2},
        {
            "claude-haiku-5-5": {
                "inputTokens": 10,
                "outputTokens": 20,
                "cacheReadInputTokens": 30,
                "cacheCreationInputTokens": 40,
            },
            "otro": {
                "inputTokens": 1,
                "outputTokens": 2,
                "cacheReadInputTokens": 3,
                "cacheCreationInputTokens": 4,
            },
        },
        4096,
        0.0123,
    )
    assert "entrada: 11" in text
    assert "salida: 22" in text
    assert "cache lectura: 33" in text
    assert "cache escritura: 44" in text
    assert "tope de salida por turno: 4096" in text
    assert "costo USD: 0.012300" in text


def test_stream_message_shows_reply_and_tool() -> None:
    class TextBlock:
        def __init__(self, text: str) -> None:
            self.text = text

    class ToolUseBlock:
        def __init__(self, name: str, tool_input: dict[str, object] | None = None) -> None:
            self.name = name
            self.input = tool_input or {}

    class ThinkingBlock:
        def __init__(self, thinking: str) -> None:
            self.thinking = thinking

    class AssistantMessage:
        def __init__(self, content: list[object]) -> None:
            self.content = content

    class ResultMessage:
        is_error = True
        errors = ["se cortó por el tope"]
        subtype = "error"

    shown = sdk_runner.format_stream_message(
        AssistantMessage(
            [
                TextBlock("  Listo.  "),
                ToolUseBlock(
                    "mcp__support__process_refund",
                    {"order_id": "ord_11", "amount": "780.00"},
                ),
                ThinkingBlock("El monto pasa de 500 USD, así que no reintento el reembolso. " * 12),
            ]
        )
    )
    assert "Listo." in shown
    assert "process_refund" in shown
    assert "order_id=ord_11" in shown
    assert "amount=780.00" in shown
    assert "decidió:" in shown
    assert len(shown.split("decidió: ", 1)[1]) < 200
    assert sdk_runner.format_stream_message(ResultMessage()) == "error: se cortó por el tope"
    assert "escalate_to_human" in sdk_runner.format_handoffs([])
    done = sdk_runner.format_handoffs([], [{"refund_id": "ref_ord_10"}])
    assert "no hizo falta" in done
    assert "bloquear" not in done
    saved = sdk_runner.format_handoffs(
        [
            {
                "order_id": "ord_11",
                "refund_amount": "780.00",
                "root_cause": "over the automatic limit",
                "recommended_action": "A person approves 780.00 USD",
            }
        ]
    )
    assert "ord_11" in saved
    assert "780.00" in saved
    assert "No hay una persona" in saved


def test_empty_runner_uses_ana_order() -> None:
    assert sdk_runner.customer_prompt(["soporte.py"]) == (sdk_runner.DEFAULT_PROMPT, False)
    assert sdk_runner.customer_prompt(["soporte.py", "hola", "Ana"]) == ("hola Ana", False)
    assert sdk_runner.customer_prompt(["soporte.py", "--chat", "hola"]) == ("hola", True)


def test_runner_is_the_only_claude_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "claude_agent_sdk" not in sys.modules
    assert "Bash" in sdk_runner.BLOCKED_BUILTINS
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(sdk_runner, "load_local_env", lambda: None)
    with pytest.raises(SystemExit, match="ANTHROPIC_API_KEY"):
        sdk_runner.run("hola")
    assert "claude_agent_sdk" not in sys.modules

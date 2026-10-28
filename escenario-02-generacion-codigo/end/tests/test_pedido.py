"""Issue 5. El pedido muestra la fecha, un espacio y el importe ya corregido."""

from datetime import datetime
from decimal import Decimal

from cargar import load_end


def test_order_reads_date_then_price() -> None:
    _, pedidos, _ = load_end()
    text = pedidos.describe(Decimal("19.90"), datetime(2026, 10, 28, 15, 0, 0))
    assert text == "2026-10-28 19.90"

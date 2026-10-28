"""Lo que start/ hace hoy. Esta suite no mira end/."""

import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load_start():
    root = str((ROOT / "start").resolve())
    for name in list(sys.modules):
        if name == "catalogo" or name.startswith("catalogo."):
            del sys.modules[name]
    sys.path.insert(0, root)
    try:
        import catalogo.fechas as fechas
        import catalogo.pedidos as pedidos
        import catalogo.precios as precios

        return precios, pedidos, fechas
    finally:
        sys.path.remove(root)


def test_start_price_drops_the_trailing_zero() -> None:
    precios, _, _ = load_start()
    assert precios.format_price(Decimal("19.90")) == "19.9"


def test_start_discount_returns_only_the_slice() -> None:
    precios, _, _ = load_start()
    assert precios.discounted_price(Decimal("19.90"), 10) == Decimal("1.99")


def test_start_day_is_not_padded() -> None:
    _, _, fechas = load_start()
    assert fechas.label_day(datetime(2026, 1, 5)) == "2026-1-5"


def test_start_day_30_is_closed() -> None:
    _, _, fechas = load_start()
    assert fechas.window_is_open(datetime(2026, 10, 1), datetime(2026, 10, 31), 30) is False


def test_start_order_puts_the_price_first() -> None:
    _, pedidos, _ = load_start()
    text = pedidos.describe(Decimal("19.90"), datetime(2026, 10, 28, 15, 0, 0))
    assert text == "19.9 @ 2026-10-28"

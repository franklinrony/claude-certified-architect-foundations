"""Issue 1. El importe conserva dos decimales."""

from decimal import Decimal

from cargar import load_end


def test_price_keeps_two_decimals() -> None:
    precios, _, _ = load_end()
    assert precios.format_price(Decimal("19.90")) == "19.90"

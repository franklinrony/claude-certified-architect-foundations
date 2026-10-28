"""Issue 2. El descuento deja el precio ya rebajado."""

from decimal import Decimal

from cargar import load_end


def test_ten_percent_off_nineteen_ninety() -> None:
    precios, _, _ = load_end()
    assert precios.discounted_price(Decimal("19.90"), 10) == Decimal("17.91")

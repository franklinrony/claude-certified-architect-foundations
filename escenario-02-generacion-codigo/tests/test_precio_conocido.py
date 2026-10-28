from decimal import Decimal

from catalogo.precios import format_price


def test_known_defect_drops_the_trailing_zero() -> None:
    """El fallo de estudio. Corregirlo es ejecución directa, no plan mode."""
    assert format_price(Decimal("19.90")) == "19.9"

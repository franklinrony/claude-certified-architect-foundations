"""Importes del catálogo. Dos defectos: el formato y el descuento."""

from decimal import Decimal


def format_price(amount: Decimal) -> str:
    return str(float(amount))


def discounted_price(amount: Decimal, percent: int) -> Decimal:
    """Devuelve solo la tajada del porcentaje, no el precio ya rebajado."""
    return (amount * Decimal(percent) / Decimal(100)).quantize(Decimal("0.01"))

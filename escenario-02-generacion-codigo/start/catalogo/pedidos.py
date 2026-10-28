"""Un pedido junta precio y fecha. El defecto está en el orden y en el separador."""

from decimal import Decimal

from catalogo.fechas import label_day
from catalogo.precios import format_price


def describe(amount: Decimal, placed_at) -> str:
    return f"{format_price(amount)} @ {label_day(placed_at)}"

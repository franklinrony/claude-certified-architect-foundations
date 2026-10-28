"""Un pedido usa el precio y la fecha. El defecto de formato no vive aquí."""

from decimal import Decimal

from catalogo.fechas import label_day
from catalogo.precios import format_price


def describe(amount: Decimal, placed_at) -> str:
    return f"{label_day(placed_at)} {format_price(amount)}"

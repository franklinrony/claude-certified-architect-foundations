"""Formato de importes del catálogo de práctica.

El defecto está a propósito: una sola función, con el fallo ya localizado.
Ese arreglo es ejecución directa. No es un rediseño.
"""

from decimal import Decimal


def format_price(amount: Decimal) -> str:
    return str(float(amount))

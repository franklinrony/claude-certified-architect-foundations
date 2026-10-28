"""Contrato del arreglo. Falla mientras end/catalogo siga igual que start/.

No cambies este archivo para poner verde la prueba. El cambio va en
end/catalogo/precios.py.
"""

import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parents[2]
PLACED_AT = datetime(2026, 10, 28, 15, 0, 0)


def load_end():
    root = str((ROOT / "end").resolve())
    for name in list(sys.modules):
        if name == "catalogo" or name.startswith("catalogo."):
            del sys.modules[name]
    sys.path.insert(0, root)
    try:
        import catalogo.pedidos as pedidos
        import catalogo.precios as precios

        return precios, pedidos
    finally:
        sys.path.remove(root)


def test_price_keeps_two_decimals() -> None:
    precios, _ = load_end()
    assert precios.format_price(Decimal("19.90")) == "19.90"


def test_order_shows_two_decimals() -> None:
    _, pedidos = load_end()
    assert pedidos.describe(Decimal("19.90"), PLACED_AT) == "2026-10-28 19.90"

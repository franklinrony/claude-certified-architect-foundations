import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parents[1]
PLACED_AT = datetime(2026, 10, 28, 15, 0, 0)


def load_start():
    """Importa el catálogo original. Esta suite no mira end/."""
    root = str((ROOT / "start").resolve())
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


def test_start_keeps_the_known_defect() -> None:
    precios, _ = load_start()
    assert precios.format_price(Decimal("19.90")) == "19.9"


def test_start_order_uses_the_defective_price() -> None:
    _, pedidos = load_start()
    assert pedidos.describe(Decimal("19.90"), PLACED_AT) == "2026-10-28 19.9"

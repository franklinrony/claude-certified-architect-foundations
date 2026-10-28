import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
CATALOG_FILES = ("__init__.py", "fechas.py", "pedidos.py", "precios.py")
PLACED_AT = datetime(2026, 10, 28, 15, 0, 0)


def load_catalogo(folder: str):
    """Importa catalogo desde start/ o end/, sin mezclar las dos copias."""
    root = str((ROOT / folder).resolve())
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


@pytest.mark.parametrize("folder", ["start", "end"])
def test_price_keeps_the_known_defect(folder: str) -> None:
    precios, _, _ = load_catalogo(folder)
    assert precios.format_price(Decimal("19.90")) == "19.9"


@pytest.mark.parametrize("folder", ["start", "end"])
def test_order_uses_the_same_price_and_day(folder: str) -> None:
    _, pedidos, _ = load_catalogo(folder)
    assert pedidos.describe(Decimal("19.90"), PLACED_AT) == "2026-10-28 19.9"


def test_end_behavior_matches_start() -> None:
    start_price, start_orders, _ = load_catalogo("start")
    end_price, end_orders, _ = load_catalogo("end")
    amount = Decimal("19.90")
    assert end_price.format_price(amount) == start_price.format_price(amount)
    assert end_orders.describe(amount, PLACED_AT) == start_orders.describe(amount, PLACED_AT)


def test_end_sources_match_start() -> None:
    for name in CATALOG_FILES:
        start = (ROOT / "start" / "catalogo" / name).read_text(encoding="utf-8")
        end = (ROOT / "end" / "catalogo" / name).read_text(encoding="utf-8")
        assert end == start

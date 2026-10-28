import importlib.util
from decimal import Decimal
from pathlib import Path


def _format_price(folder: str):
    path = Path(__file__).parents[1] / folder / "catalogo" / "precios.py"
    spec = importlib.util.spec_from_file_location(f"precios_{folder}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.format_price


def test_start_keeps_the_original_defect() -> None:
    """start/ no se corrige. El arreglo, si se hace, queda en end/."""
    assert _format_price("start")(Decimal("19.90")) == "19.9"

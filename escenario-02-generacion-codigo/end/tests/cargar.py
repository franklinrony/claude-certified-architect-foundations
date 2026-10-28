"""Carga catalogo desde end/. No es una prueba."""

import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]


def load_end():
    root = str((ROOT / "end").resolve())
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

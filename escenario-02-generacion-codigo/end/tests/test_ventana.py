"""Issue 4. La ventana de 30 días sigue abierta en el día 30."""

from datetime import datetime

from cargar import load_end


def test_day_30_is_still_open() -> None:
    _, _, fechas = load_end()
    placed = datetime(2026, 10, 1)
    assert fechas.window_is_open(placed, datetime(2026, 10, 31), 30) is True


def test_day_31_is_closed() -> None:
    _, _, fechas = load_end()
    placed = datetime(2026, 10, 1)
    assert fechas.window_is_open(placed, datetime(2026, 11, 1), 30) is False

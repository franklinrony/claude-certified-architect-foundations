"""Issue 3. El día se escribe con mes y día de dos cifras."""

from datetime import datetime

from cargar import load_end


def test_january_fifth_is_zero_padded() -> None:
    _, _, fechas = load_end()
    assert fechas.label_day(datetime(2026, 1, 5)) == "2026-01-05"

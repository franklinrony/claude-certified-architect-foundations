"""Fechas del catálogo. Dos defectos: el texto del día y el día 30 de la ventana."""

from datetime import datetime


def label_day(moment: datetime) -> str:
    return f"{moment.year}-{moment.month}-{moment.day}"


def window_is_open(placed_at: datetime, today: datetime, days: int = 30) -> bool:
    elapsed = (today.date() - placed_at.date()).days
    return 0 <= elapsed < days

"""Fechas del catálogo. Otro archivo, para que el código no sea una sola función."""

from datetime import datetime


def label_day(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d")

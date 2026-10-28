"""Conexión a ccar_f. La clave se lee de .env y no se imprime."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


SCENARIO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = SCENARIO_ROOT / ".env"
SQL_PATH = SCENARIO_ROOT / "db" / "ccar_f.sql"
DATABASE_NAME = "ccar_f"


class TransientStoreError(RuntimeError):
    """Timeout o caída de Postgres. Se puede reintentar."""


def load_local_env(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"'))


def database_url() -> str:
    load_local_env()
    url = os.environ.get("CCAR_DATABASE_URL", "").strip()
    if not url:
        raise SystemExit(
            "Falta CCAR_DATABASE_URL. Copia .env.example a .env en el escenario 1."
        )
    return url


def admin_url(url: str) -> str:
    """Misma credencial, base de mantenimiento postgres, para CREATE DATABASE."""
    if "/" not in url:
        raise SystemExit("CCAR_DATABASE_URL no tiene base de datos.")
    head, _, _database = url.rpartition("/")
    return f"{head}/postgres"


def connect(url: str | None = None) -> psycopg.Connection:
    target = url or database_url()
    try:
        # El primer SELECT abre transacción si autocommit está apagado, y close() la revierte.
        # El reembolso se veía en la respuesta y no quedaba en la base.
        return psycopg.connect(target, row_factory=dict_row, autocommit=True)
    except psycopg.OperationalError as exc:
        raise SystemExit(
            f"No se pudo conectar a PostgreSQL ({DATABASE_NAME} en localhost)."
        ) from exc

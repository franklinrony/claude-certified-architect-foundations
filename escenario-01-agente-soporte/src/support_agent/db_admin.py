"""Crea ccar_f y aplica los esquemas. No borra otras bases."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlparse

import psycopg

from support_agent.db import DATABASE_NAME, SQL_PATH, admin_url, database_url


PSQL_CANDIDATES = (
    shutil.which("psql"),
    r"C:\Program Files\PostgreSQL\16\bin\psql.exe",
)

RESET_SCENARIO_01 = """
TRUNCATE
    escenario_01.handoffs,
    escenario_01.refunds,
    escenario_01.order_items,
    escenario_01.payments,
    escenario_01.shipments,
    escenario_01.orders,
    escenario_01.customers
RESTART IDENTITY
"""


def _psql() -> str:
    for candidate in PSQL_CANDIDATES:
        if candidate:
            return candidate
    raise SystemExit("No está psql. Hace falta el cliente de PostgreSQL 16.")


def _psql_invocation(url: str) -> tuple[list[str], dict[str, str], str | None]:
    """Opciones antes de la base. psql trata el primer argumento suelto como dbname."""
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise SystemExit("CCAR_DATABASE_URL debe empezar por postgresql://")
    database = unquote(parsed.path.lstrip("/"))
    user = unquote(parsed.username or "")
    if not database or not user:
        raise SystemExit("CCAR_DATABASE_URL necesita usuario y base.")
    secret = unquote(parsed.password) if parsed.password is not None else None
    env = os.environ.copy()
    env["PGCLIENTENCODING"] = "UTF8"
    if secret is not None:
        env["PGPASSWORD"] = secret
    command = [
        _psql(),
        "-w",
        "-v",
        "ON_ERROR_STOP=1",
        "-h",
        parsed.hostname or "localhost",
        "-p",
        str(parsed.port or 5432),
        "-U",
        user,
        "-d",
        database,
    ]
    return command, env, secret


def _redact(text: str, secret: str | None) -> str:
    if secret and secret in text:
        return text.replace(secret, "***")
    return text


def _run_psql(url: str, *args: str) -> None:
    command, env, secret = _psql_invocation(url)
    completed = subprocess.run(
        [*command, *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    detail = _redact(
        "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part and part.strip()),
        secret,
    )
    if completed.returncode != 0:
        raise SystemExit(detail or "psql terminó con error")
    if detail:
        print(detail)


def _scenario_schemas(url: str) -> list[str]:
    with psycopg.connect(url) as conn:
        rows = conn.execute(
            "SELECT nspname FROM pg_namespace WHERE nspname LIKE 'escenario_%%' ORDER BY 1"
        ).fetchall()
    return [row[0] for row in rows]


def ensure_database() -> None:
    url = database_url()
    try:
        with psycopg.connect(admin_url(url), autocommit=True) as conn:
            exists = conn.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (DATABASE_NAME,),
            ).fetchone()
            if exists is None:
                conn.execute(f"CREATE DATABASE {DATABASE_NAME}")
    except psycopg.OperationalError as exc:
        raise SystemExit(
            "No se pudo conectar a PostgreSQL en localhost para crear ccar_f."
        ) from exc


def apply_sql(reset_scenario_01: bool) -> None:
    url = database_url()
    if reset_scenario_01:
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(RESET_SCENARIO_01)
    _run_psql(url, "-f", str(SQL_PATH))
    names = _scenario_schemas(url)
    expected = [f"escenario_0{index}" for index in range(1, 7)]
    if names != expected:
        raise SystemExit(f"El SQL no dejó los seis esquemas. Hay: {names or 'ninguno'}.")


def main() -> None:
    reset = "--reset" in sys.argv[1:]
    ensure_database()
    apply_sql(reset_scenario_01=reset)
    print(f"Base {DATABASE_NAME} lista. Esquemas escenario_01 a escenario_06.")
    if reset:
        print("escenario_01 volvió a la semilla.")


if __name__ == "__main__":
    main()

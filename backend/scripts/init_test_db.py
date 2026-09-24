from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import settings


def _require_test_database_url() -> str:
    if not settings.TEST_DATABASE_URL:
        raise RuntimeError(
            "TEST_DATABASE_URL must be configured before initializing tests"
        )
    return str(settings.TEST_DATABASE_URL)


def _psycopg_dsn(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def ensure_test_database_exists(test_database_url: str) -> str:
    url = make_url(test_database_url)
    database_name = url.database
    if not database_name:
        raise RuntimeError("TEST_DATABASE_URL must include a database name")

    admin_url = url.set(database="postgres")
    admin_dsn = _psycopg_dsn(admin_url.render_as_string(hide_password=False))

    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (database_name,),
            )
            exists = cursor.fetchone() is not None
            if not exists:
                cursor.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
                )

    return database_name


def upgrade_test_database(test_database_url: str) -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["DATABASE_URL"] = test_database_url

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        check=True,
    )


def main() -> None:
    test_database_url = _require_test_database_url()
    ensure_test_database_exists(test_database_url)
    upgrade_test_database(test_database_url)


if __name__ == "__main__":
    main()

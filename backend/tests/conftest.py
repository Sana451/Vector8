import os
from collections.abc import Generator
from pathlib import Path
from string import Template

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlmodel import Session, delete

# TEST_DATABASE_URL must be selected before importing app.core.db, otherwise
# the global application engine will bind to the development database.

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _load_env_file_values() -> dict[str, str]:
    values: dict[str, str] = {}
    interpolation_scope = dict(os.environ)

    if not ENV_FILE.exists():
        return values

    for raw_line in ENV_FILE.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        expanded = Template(value).safe_substitute({**interpolation_scope, **values})
        values[key] = expanded

    return values


def _normalize_postgres_url(database_url: str) -> str:
    for scheme in ("postgres://", "postgresql://"):
        if database_url.startswith(scheme):
            return database_url.replace(scheme, "postgresql+psycopg://", 1)
    return database_url


def _load_test_database_url() -> str:
    env_values = _load_env_file_values()
    raw_test_database_url = os.environ.get("TEST_DATABASE_URL") or env_values.get(
        "TEST_DATABASE_URL"
    )
    if not raw_test_database_url:
        raise RuntimeError("TEST_DATABASE_URL must be configured before running tests")
    return _normalize_postgres_url(raw_test_database_url)


TEST_DATABASE_URL = _load_test_database_url()
EXPECTED_TEST_DATABASE = make_url(TEST_DATABASE_URL).database
if not EXPECTED_TEST_DATABASE:
    raise RuntimeError("TEST_DATABASE_URL must include a database name")

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["TEST_DATABASE_URL"] = TEST_DATABASE_URL

# noqa: E402 - Environment variables must be set before importing app modules
from app.core.config import settings  # noqa: E402
from app.core.db import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Item, User  # noqa: E402
from tests.utils.user import authentication_token_from_email  # noqa: E402
from tests.utils.utils import get_superuser_token_headers  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session]:
    with Session(engine) as session:
        current_database = (
            session.connection()
            .exec_driver_sql("SELECT current_database()")
            .scalar_one()
        )
        if current_database != EXPECTED_TEST_DATABASE:
            raise RuntimeError(
                "Pytest is connected to the wrong database: "
                f"expected {EXPECTED_TEST_DATABASE!r}, got {current_database!r}"
            )
        init_db(session)
        yield session
        statement = delete(Item)
        session.execute(statement)
        statement = delete(User)
        session.execute(statement)
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )

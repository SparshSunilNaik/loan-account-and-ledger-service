import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from ledgercore.db.session import get_session
from ledgercore.main import app


@pytest.fixture(scope="session")
def pg_engine():
    """Create and destroy an isolated DB; never clear a developer database."""
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run real PostgreSQL integration tests")
    admin_url = make_url(url)
    if admin_url.get_backend_name() != "postgresql":
        pytest.fail("Integration tests require PostgreSQL")
    name = "ledgercore_test_" + uuid4().hex
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    test_url = admin_url.set(database=name).render_as_string(hide_password=False)
    old_demo = os.environ.get("DEMO_AUTH_ENABLED")
    os.environ["DEMO_AUTH_ENABLED"] = "true"
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_url
    engine = create_engine(test_url, connect_args={"options": "-c timezone=UTC"})
    try:
        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")
        command.check(cfg)
        command.downgrade(cfg, "base")
        with engine.connect() as conn:
            assert (
                conn.scalar(
                    text(
                        "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name <> 'alembic_version'"
                    )
                )
                == 0
            )
        command.upgrade(cfg, "head")
        yield engine
    finally:
        engine.dispose()
        if old_demo is None:
            os.environ.pop("DEMO_AUTH_ENABLED", None)
        else:
            os.environ["DEMO_AUTH_ENABLED"] = old_demo
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def db(pg_engine):
    with pg_engine.connect() as connection:
        transaction = connection.begin()
        with Session(
            connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            yield session
        transaction.rollback()


@pytest.fixture
def client(db):
    def override():
        with Session(
            db.bind, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as request_session:
            yield request_session

    app.dependency_overrides[get_session] = override
    with TestClient(app, headers={"X-Demo-User": "demo-officer"}) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def parallel_env(pg_engine, monkeypatch):
    """Committed requests need their own database, isolated from rollback-based tests."""
    name = "ledgercore_parallel_" + uuid4().hex
    admin = create_engine(
        pg_engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = pg_engine.url.set(database=name)
    engine = create_engine(
        url,
        pool_size=25,
        max_overflow=5,
        connect_args={
            "options": "-c timezone=UTC",
            "application_name": "ledgercore_parallel",
        },
    )
    monkeypatch.setenv("DATABASE_URL", url.render_as_string(hide_password=False))
    command.upgrade(Config("alembic.ini"), "head")

    def dependency():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = dependency
    try:
        with TestClient(app, headers={"X-Demo-User": "demo-officer"}) as client:
            yield client, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()

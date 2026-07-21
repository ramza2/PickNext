from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.session import get_db
from app.main import create_app
from app.models import User


@pytest.fixture(scope="session")
def engine():
    settings = get_settings()
    eng = create_engine(
        settings.sqlalchemy_database_url,
        poolclass=NullPool,
        future=True,
    )
    with eng.connect() as conn:
        conn.execute(text("SELECT 1"))
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(bind=connection, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans) -> None:  # type: ignore[no-untyped-def]
        if trans.nested and not trans._parent.nested:  # noqa: SLF001
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def user(db: Session) -> User:
    entity = User(
        email="test-user@picknext.local",
        display_name="Test User",
        password_hash="hash",
        is_active=True,
    )
    db.add(entity)
    db.flush()
    return entity

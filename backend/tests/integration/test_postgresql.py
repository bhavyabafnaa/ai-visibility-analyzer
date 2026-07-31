import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import cast

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from geolens_api.database import get_session
from geolens_api.main import app

pytestmark = pytest.mark.integration

configured_test_database_url = os.getenv("TEST_DATABASE_URL")
if not configured_test_database_url:
    pytest.skip(
        "TEST_DATABASE_URL is not set; PostgreSQL integration tests require a disposable database",
        allow_module_level=True,
    )
TEST_DATABASE_URL = cast(str, configured_test_database_url)

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module", autouse=True)
def migrated_database() -> Iterator[None]:
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL.replace("%", "%%"))
    command.upgrade(config, "head")
    yield
    command.downgrade(config, "base")


@pytest_asyncio.fixture
async def postgres_session(migrated_database: None) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(TEST_DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(postgres_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield postgres_session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def test_initial_migration_creates_expected_postgresql_schema() -> None:
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as connection:
        table_names = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_table_names()
        )
        project_columns = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_columns("projects")
        )
        analysis_run_columns = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_columns("analysis_runs")
        )
    await engine.dispose()

    assert {
        "alembic_version",
        "analysis_runs",
        "analysis_responses",
        "analysis_citations",
        "analysis_entities",
        "analysis_scores",
        "analysis_claims",
        "claim_evidence",
        "competitors",
        "crawl_errors",
        "crawl_jobs",
        "crawl_pages",
        "projects",
        "sites",
    }.issubset(table_names)
    timestamps = {
        column["name"]: column for column in project_columns if column["name"].endswith("_at")
    }
    created_at_type = timestamps["created_at"]["type"]
    updated_at_type = timestamps["updated_at"]["type"]
    assert hasattr(created_at_type, "timezone") and created_at_type.timezone
    assert hasattr(updated_at_type, "timezone") and updated_at_type.timezone
    assert {
        "celery_task_id",
        "provider_configurations",
        "prompts",
        "claim_classifier_configuration",
    }.issubset({column["name"] for column in analysis_run_columns})


async def test_project_api_and_readiness_use_postgresql(client: AsyncClient) -> None:
    readiness = await client.get("/ready")
    created = await client.post(
        "/projects",
        json={
            "name": "PostgreSQL integration",
            "site": {"url": "https://integration.example"},
            "competitors": [],
        },
    )
    retrieved = await client.get(f"/projects/{created.json()['id']}")
    listed = await client.get("/projects")

    assert readiness.status_code == 200
    assert readiness.json() == {"status": "ok"}
    assert created.status_code == 201
    assert created.json()["created_at"].endswith(("+00:00", "Z"))
    assert retrieved.json() == created.json()
    assert created.json() in listed.json()

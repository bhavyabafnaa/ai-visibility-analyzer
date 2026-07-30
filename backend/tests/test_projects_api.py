from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from geolens_api.database import get_session
from geolens_api.main import app


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def create_project(client: AsyncClient, name: str = "Acme visibility") -> dict[str, object]:
    response = await client.post(
        "/projects",
        json={
            "name": name,
            "site": {"url": "https://acme.example"},
            "competitors": [
                {
                    "name": "Example competitor",
                    "url": "https://competitor.example",
                }
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


async def test_create_project_returns_persisted_aggregate(client: AsyncClient) -> None:
    project = await create_project(client)

    assert UUID(str(project["id"])).version == 4
    assert project["name"] == "Acme visibility"
    assert project["site"]["url"] == "https://acme.example/"  # type: ignore[index]
    assert project["competitors"][0]["name"] == "Example competitor"  # type: ignore[index]
    assert project["created_at"]
    assert project["updated_at"]


async def test_get_project_returns_created_project(client: AsyncClient) -> None:
    created = await create_project(client)

    response = await client.get(f"/projects/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


async def test_get_project_returns_404_for_unknown_uuid(client: AsyncClient) -> None:
    project_id = uuid4()

    response = await client.get(f"/projects/{project_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": f"Project {project_id} was not found"}


async def test_list_projects_is_paginated(client: AsyncClient) -> None:
    first = await create_project(client, "First")
    second = await create_project(client, "Second")

    response = await client.get("/projects", params={"offset": 1, "limit": 1})

    assert response.status_code == 200
    result = response.json()
    assert len(result) == 1
    assert result[0]["id"] in {first["id"], second["id"]}


async def test_create_project_rejects_blank_name(client: AsyncClient) -> None:
    response = await client.post("/projects", json={"name": "   "})

    assert response.status_code == 422


async def test_create_project_rejects_non_string_name(client: AsyncClient) -> None:
    response = await client.post("/projects", json={"name": 123})

    assert response.status_code == 422

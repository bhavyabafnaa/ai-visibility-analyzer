from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from geolens_api.database import get_session
from geolens_api.main import app
from geolens_api.models import Project, Site
from geolens_api.providers import DisabledProvider, MockProvider, ProviderRegistry
from geolens_api.queues import get_analysis_queue
from geolens_api.routers.analyses import get_provider_registry


class RecordingAnalysisQueue:
    def __init__(self) -> None:
        self.analysis_ids: list[UUID] = []
        self.fail = False

    def enqueue(self, analysis_id: UUID) -> str:
        if self.fail:
            raise ConnectionError("Redis unavailable")
        self.analysis_ids.append(analysis_id)
        return "analysis-task-id"


@pytest.fixture
async def provider_registry() -> AsyncIterator[ProviderRegistry]:
    registry = ProviderRegistry(
        [
            MockProvider(model_identifier="mock-api-test"),
            DisabledProvider(
                name="openai",
                model_identifier="openai-api-test",
                reason="OPENAI_API_KEY is not configured",
            ),
        ]
    )
    yield registry
    await registry.aclose()


@pytest.fixture
async def client(
    session: AsyncSession,
    provider_registry: ProviderRegistry,
) -> AsyncIterator[tuple[AsyncClient, Project, RecordingAnalysisQueue]]:
    project = Project(name="GeoLens", aliases=[])
    project.site = Site(url="https://geolens.test")
    session.add(project)
    await session.commit()
    queue = RecordingAnalysisQueue()

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_provider_registry] = lambda: provider_registry
    app.dependency_overrides[get_analysis_queue] = lambda: queue
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client, project, queue
    app.dependency_overrides.clear()


async def test_start_analysis_queues_selected_prompt_matrix(
    client: tuple[AsyncClient, Project, RecordingAnalysisQueue],
) -> None:
    test_client, project, queue = client

    response = await test_client.post(
        "/analyses",
        json={
            "project_id": str(project.id),
            "providers": ["mock"],
            "prompts": ["What is GeoLens?", "Another prompt"],
        },
    )

    assert response.status_code == 202
    body = response.json()
    analysis_id = UUID(body["analysis_id"])
    assert queue.analysis_ids == [analysis_id]
    assert body["status"] == "pending"
    assert body["started_at"] is None
    assert body["completed_at"] is None
    assert body["celery_task_id"] == "analysis-task-id"
    assert body["provider_configurations"] == [
        {"name": "mock", "model_identifier": "mock-api-test"}
    ]
    assert body["prompts"] == ["What is GeoLens?", "Another prompt"]
    assert body["results"] == []
    assert body["persisted"] is True

    status_response = await test_client.get(f"/analyses/{analysis_id}")
    assert status_response.status_code == 200
    assert status_response.json() == body


async def test_disabled_selected_provider_is_queued_without_fallback(
    client: tuple[AsyncClient, Project, RecordingAnalysisQueue],
) -> None:
    test_client, project, queue = client

    response = await test_client.post(
        "/analyses",
        json={
            "project_id": str(project.id),
            "providers": ["openai"],
            "prompts": ["What is GeoLens?"],
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["provider_configurations"] == [
        {"name": "openai", "model_identifier": "openai-api-test"}
    ]
    assert queue.analysis_ids == [UUID(body["analysis_id"])]


async def test_unknown_selected_provider_is_rejected(
    client: tuple[AsyncClient, Project, RecordingAnalysisQueue],
) -> None:
    test_client, project, queue = client

    response = await test_client.post(
        "/analyses",
        json={
            "project_id": str(project.id),
            "providers": ["unknown"],
            "prompts": ["What is GeoLens?"],
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Unknown provider: unknown"}
    assert queue.analysis_ids == []


async def test_provider_availability_is_explicit(
    client: tuple[AsyncClient, Project, RecordingAnalysisQueue],
) -> None:
    test_client, _, _ = client

    response = await test_client.get("/providers")

    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "mock",
            "model_identifier": "mock-api-test",
            "enabled": True,
            "disabled_reason": None,
        },
        {
            "name": "openai",
            "model_identifier": "openai-api-test",
            "enabled": False,
            "disabled_reason": "OPENAI_API_KEY is not configured",
        },
    ]


async def test_analysis_rejects_duplicate_or_blank_inputs(
    client: tuple[AsyncClient, Project, RecordingAnalysisQueue],
) -> None:
    test_client, project, _ = client
    duplicate_response = await test_client.post(
        "/analyses",
        json={
            "project_id": str(project.id),
            "providers": ["mock", "MOCK"],
            "prompts": ["What is GeoLens?"],
        },
    )
    blank_response = await test_client.post(
        "/analyses",
        json={
            "project_id": str(project.id),
            "providers": ["mock"],
            "prompts": [" "],
        },
    )

    assert duplicate_response.status_code == 422
    assert blank_response.status_code == 422


async def test_analysis_rejects_unbounded_prompt_input(
    client: tuple[AsyncClient, Project, RecordingAnalysisQueue],
) -> None:
    test_client, project, _ = client
    response = await test_client.post(
        "/analyses",
        json={
            "project_id": str(project.id),
            "providers": ["mock"],
            "prompts": ["x" * 10_001],
        },
    )

    assert response.status_code == 422
    assert "prompts cannot exceed 10000 characters" in response.text


async def test_analysis_queue_failure_is_explicit(
    client: tuple[AsyncClient, Project, RecordingAnalysisQueue],
) -> None:
    test_client, project, queue = client

    queue.fail = True
    response = await test_client.post(
        "/analyses",
        json={
            "project_id": str(project.id),
            "providers": ["mock"],
            "prompts": ["What is GeoLens?"],
        },
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "The analysis could not be queued"}

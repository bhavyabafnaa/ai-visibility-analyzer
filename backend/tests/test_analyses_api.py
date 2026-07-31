from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from geolens_api.main import app
from geolens_api.providers import DisabledProvider, MockProvider, ProviderRegistry
from geolens_api.routers.analyses import get_provider_registry


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
async def client(provider_registry: ProviderRegistry) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_provider_registry] = lambda: provider_registry
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def test_start_analysis_executes_selected_prompt_matrix(client: AsyncClient) -> None:
    response = await client.post(
        "/analyses",
        json={
            "providers": ["mock"],
            "prompts": ["What is GeoLens?", "Another prompt"],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert UUID(body["analysis_id"]).version == 4
    assert body["status"] == "succeeded"
    assert body["started_at"] <= body["completed_at"]
    assert [result["prompt"] for result in body["results"]] == [
        "What is GeoLens?",
        "Another prompt",
    ]
    assert all(result["provider"] == "mock" for result in body["results"])
    assert all(result["status"] == "succeeded" for result in body["results"])
    assert all("raw_response" in result for result in body["results"])


async def test_disabled_selected_provider_is_returned_without_fallback(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/analyses",
        json={"providers": ["openai"], "prompts": ["What is GeoLens?"]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert len(body["results"]) == 1
    assert body["results"][0]["provider"] == "openai"
    assert body["results"][0]["status"] == "disabled"
    assert body["results"][0]["error"]["code"] == "provider_disabled"


async def test_unknown_selected_provider_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/analyses",
        json={"providers": ["unknown"], "prompts": ["What is GeoLens?"]},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Unknown provider: unknown"}


async def test_provider_availability_is_explicit(client: AsyncClient) -> None:
    response = await client.get("/providers")

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


async def test_analysis_rejects_duplicate_or_blank_inputs(client: AsyncClient) -> None:
    duplicate_response = await client.post(
        "/analyses",
        json={"providers": ["mock", "MOCK"], "prompts": ["What is GeoLens?"]},
    )
    blank_response = await client.post(
        "/analyses",
        json={"providers": ["mock"], "prompts": [" "]},
    )

    assert duplicate_response.status_code == 422
    assert blank_response.status_code == 422


async def test_analysis_rejects_unbounded_prompt_input(client: AsyncClient) -> None:
    response = await client.post(
        "/analyses",
        json={"providers": ["mock"], "prompts": ["x" * 10_001]},
    )

    assert response.status_code == 422
    assert "prompts cannot exceed 10000 characters" in response.text

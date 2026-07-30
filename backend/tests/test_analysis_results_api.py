from collections.abc import AsyncIterator
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from geolens_api.database import get_session
from geolens_api.main import app
from geolens_api.models import Competitor, CrawlJob, CrawlPage, Project, Site
from geolens_api.providers import MockProvider, ProviderRegistry
from geolens_api.providers.contract import (
    Citation,
    ProviderResponse,
    ProviderResponseStatus,
)
from geolens_api.providers.mock import MockFixture
from geolens_api.routers.analyses import get_provider_registry


class SupportingClassifierProvider:
    name = "classifier"
    model_identifier = "classifier-test-v1"
    enabled = True
    disabled_reason = None

    def __init__(self) -> None:
        self.call_count = 0

    async def execute(self, prompt: str) -> ProviderResponse:
        del prompt
        self.call_count += 1
        return ProviderResponse(
            provider=self.name,
            model_identifier=self.model_identifier,
            response_text=(
                '{"classification":"supported","confidence":0.9,'
                '"explanation":"Stored evidence supports the claim."}'
            ),
            latency_ms=1,
            status=ProviderResponseStatus.SUCCEEDED,
        )


@pytest.fixture
async def results_client(
    session: AsyncSession,
) -> AsyncIterator[tuple[AsyncClient, Project, CrawlJob, SupportingClassifierProvider]]:
    project = Project(name="Acme Cloud", aliases=["Acme"])
    project.site = Site(url="https://acme.test")
    project.competitors = [
        Competitor(
            name="Globex",
            aliases=["Globex AI"],
            url="https://globex.test",
        )
    ]
    session.add(project)
    await session.flush()
    crawl = CrawlJob(
        site_id=project.site.id,
        status="succeeded",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    session.add(crawl)
    await session.flush()
    session.add(
        CrawlPage(
            crawl_job_id=crawl.id,
            url="https://acme.test/about",
            canonical_url=None,
            title="About Acme",
            description=None,
            headings=[],
            main_text=("Acme Cloud was founded in 2020. Globex has older tools according to Acme."),
            structured_data=[],
            internal_links=[],
            content_hash="a" * 64,
            status_code=200,
            depth=0,
            content_type="text/html",
            response_size=100,
        )
    )
    await session.commit()

    classifier = SupportingClassifierProvider()
    provider = MockProvider(
        model_identifier="mock-results-test",
        fixtures={
            "Compare vendors": MockFixture(
                response_text=("Acme Cloud was founded in 2020. Globex has older tools."),
                citations=[
                    Citation(
                        url="https://WWW.Acme.Test/about",
                        title="About Acme",
                        cited_text="Acme Cloud was founded in 2020.",
                    )
                ],
            )
        },
    )
    registry = ProviderRegistry([provider, classifier])

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_provider_registry] = lambda: registry
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, project, crawl, classifier
    app.dependency_overrides.clear()
    await registry.aclose()


async def test_persisted_analysis_exposes_citations_entities_scores_and_claims(
    results_client: tuple[AsyncClient, Project, CrawlJob, SupportingClassifierProvider],
) -> None:
    client, project, crawl, classifier = results_client

    started = await client.post(
        "/analyses",
        json={
            "project_id": str(project.id),
            "crawl_job_id": str(crawl.id),
            "providers": ["mock"],
            "prompts": ["Compare vendors"],
            "claim_classifier_provider": "classifier",
        },
    )

    assert started.status_code == 201
    analysis = started.json()
    assert analysis["persisted"] is True
    analysis_id = analysis["analysis_id"]

    citations = (await client.get(f"/analyses/{analysis_id}/citations")).json()
    entities = (await client.get(f"/analyses/{analysis_id}/entities")).json()
    scores = (await client.get(f"/analyses/{analysis_id}/scores")).json()
    claims = (await client.get(f"/analyses/{analysis_id}/claims")).json()

    assert citations[0]["normalized_domain"] == "acme.test"
    assert [(entity["name"], entity["kind"]) for entity in entities[:2]] == [
        ("Acme Cloud", "target"),
        ("Globex", "competitor"),
    ]
    score_by_name = {score["name"]: score for score in scores}
    assert score_by_name["visibility_rate"]["value"] == 1
    assert score_by_name["target_domain_citation_coverage"]["value"] == 1
    assert score_by_name["citation_share"]["value"] == 1
    assert score_by_name["entity_coverage"]["value"] == 1
    assert score_by_name["rank_weighted_share_of_ai_voice"]["value"] == pytest.approx(2 / 3)
    risk = score_by_name["claim_support_risk"]
    assert risk["is_objective_truth"] is False
    assert "not objective truth" in risk["disclaimer"]
    assert len(claims) == 2
    assert all(claim["classification"] == "supported" for claim in claims)
    assert all(claim["evidence"] for claim in claims)
    assert classifier.call_count == 2


async def test_analysis_result_endpoints_return_404_for_unknown_run(
    results_client: tuple[AsyncClient, Project, CrawlJob, SupportingClassifierProvider],
) -> None:
    client, _, _, _ = results_client
    analysis_id = uuid4()

    response = await client.get(f"/analyses/{analysis_id}/scores")

    assert response.status_code == 404
    assert response.json() == {"detail": f"Analysis {analysis_id} was not found"}

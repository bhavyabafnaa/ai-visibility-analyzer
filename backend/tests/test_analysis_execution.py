from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from geolens_api.celery_app import celery_app
from geolens_api.models import Project, Site
from geolens_api.models.analysis_run import AnalysisRunStatus
from geolens_api.providers import MockProvider, ProviderModelMismatchError, ProviderRegistry
from geolens_api.repositories.analyses import AnalysisRepository
from geolens_api.services.analyses import AnalysisService
from geolens_api.tasks.analysis import run_analysis


def test_analysis_worker_task_is_registered_by_name() -> None:
    assert run_analysis.name == "geolens.run_analysis"
    assert celery_app.tasks["geolens.run_analysis"].name == run_analysis.name


async def test_worker_rejects_queued_provider_model_drift(session: AsyncSession) -> None:
    project = Project(name="GeoLens", aliases=[])
    project.site = Site(url="https://geolens.test")
    session.add(project)
    await session.commit()
    run = await AnalysisRepository(session).create_run(
        project_id=project.id,
        crawl_job_id=None,
        provider_configurations=[{"name": "mock", "model_identifier": "model-used-when-queued"}],
        prompts=["What is GeoLens?"],
        claim_classifier_configuration=None,
    )
    analysis_id = UUID(str(run.id))
    await session.commit()
    registry = ProviderRegistry([MockProvider(model_identifier="worker-model")])

    with pytest.raises(ProviderModelMismatchError, match="not queued model"):
        await AnalysisService(registry, session).execute(analysis_id)

    await session.refresh(run)
    assert run.status is AnalysisRunStatus.FAILED
    assert run.started_at is None
    assert run.completed_at is not None
    assert run.error_message == (
        "Provider mock is configured for model worker-model, "
        "not queued model model-used-when-queued"
    )
    await registry.aclose()

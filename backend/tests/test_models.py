from sqlalchemy import DateTime, Uuid

from geolens_api.models import (
    AnalysisCitation,
    AnalysisClaim,
    AnalysisEntity,
    AnalysisResponse,
    AnalysisRun,
    AnalysisScore,
    ClaimEvidence,
    Competitor,
    CrawlError,
    CrawlJob,
    CrawlPage,
    Project,
    Site,
)


def test_all_models_use_uuid_primary_keys() -> None:
    for model in (
        Project,
        Site,
        Competitor,
        CrawlJob,
        CrawlPage,
        CrawlError,
        AnalysisRun,
        AnalysisResponse,
        AnalysisCitation,
        AnalysisEntity,
        AnalysisScore,
        AnalysisClaim,
        ClaimEvidence,
    ):
        primary_key = model.__table__.c.id

        assert primary_key.primary_key
        assert isinstance(primary_key.type, Uuid)
        assert primary_key.type.as_uuid
        assert primary_key.default is not None
        assert primary_key.default.is_callable


def test_all_timestamps_are_timezone_aware() -> None:
    for model in (
        Project,
        Site,
        Competitor,
        CrawlJob,
        CrawlPage,
        CrawlError,
        AnalysisRun,
        AnalysisResponse,
        AnalysisCitation,
        AnalysisEntity,
        AnalysisScore,
        AnalysisClaim,
        ClaimEvidence,
    ):
        for column_name in ("created_at", "updated_at"):
            timestamp = model.__table__.c[column_name]

            assert isinstance(timestamp.type, DateTime)
            assert timestamp.type.timezone
            assert timestamp.nullable is False

    for model in (CrawlJob, AnalysisRun):
        for column_name in ("started_at", "completed_at"):
            timestamp = model.__table__.c[column_name]

            assert isinstance(timestamp.type, DateTime)
            assert timestamp.type.timezone

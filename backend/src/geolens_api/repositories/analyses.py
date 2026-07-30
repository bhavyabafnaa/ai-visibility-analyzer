from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from geolens_api.analysis.claims import ClaimAssessment, ClaimSegment, EvidenceMatch
from geolens_api.analysis.entities import ExtractedEntity
from geolens_api.analysis.matching import mention_position
from geolens_api.analysis.metrics import MetricResult
from geolens_api.models.analysis_citation import AnalysisCitation
from geolens_api.models.analysis_claim import AnalysisClaim, ClaimEvidence
from geolens_api.models.analysis_entity import AnalysisEntity
from geolens_api.models.analysis_response import AnalysisResponse
from geolens_api.models.analysis_run import AnalysisRun, AnalysisRunStatus
from geolens_api.models.analysis_score import AnalysisScore
from geolens_api.models.crawl_job import CrawlJob
from geolens_api.models.crawl_page import CrawlPage
from geolens_api.models.project import Project
from geolens_api.schemas.analysis import PromptExecutionResponse


class AnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_project(self, project_id: UUID) -> Project | None:
        statement = (
            select(Project)
            .where(Project.id == project_id)
            .options(
                selectinload(Project.site),
                selectinload(Project.competitors),
            )
        )
        return await self._session.scalar(statement)

    async def get_crawl_job(self, crawl_job_id: UUID) -> CrawlJob | None:
        statement = (
            select(CrawlJob).where(CrawlJob.id == crawl_job_id).options(selectinload(CrawlJob.site))
        )
        return await self._session.scalar(statement)

    async def list_crawl_pages(self, crawl_job_id: UUID | None) -> list[CrawlPage]:
        if crawl_job_id is None:
            return []
        statement = (
            select(CrawlPage)
            .where(CrawlPage.crawl_job_id == crawl_job_id)
            .order_by(CrawlPage.url, CrawlPage.id)
        )
        return list((await self._session.scalars(statement)).all())

    async def create_run(
        self,
        *,
        project_id: UUID,
        crawl_job_id: UUID | None,
        started_at: datetime,
    ) -> AnalysisRun:
        run = AnalysisRun(
            project_id=project_id,
            crawl_job_id=crawl_job_id,
            status=AnalysisRunStatus.RUNNING,
            started_at=started_at,
        )
        self._session.add(run)
        await self._session.flush()
        return run

    def add_response(
        self,
        *,
        analysis_run_id: UUID,
        ordinal: int,
        result: PromptExecutionResponse,
        normalization_rule_version: str,
        normalized_domains: tuple[str | None, ...],
    ) -> AnalysisResponse:
        response = AnalysisResponse(
            analysis_run_id=analysis_run_id,
            ordinal=ordinal,
            prompt=result.prompt,
            provider=result.provider,
            model_identifier=result.model_identifier,
            response_text=result.response_text,
            status=result.status.value,
            raw_response=result.raw_response,
            token_usage=result.token_usage.model_dump(mode="json"),
            latency_ms=result.latency_ms,
            error=result.error.model_dump(mode="json") if result.error is not None else None,
        )
        response.citations = [
            AnalysisCitation(
                ordinal=citation_ordinal,
                url=citation.url,
                normalized_domain=normalized_domains[citation_ordinal],
                title=citation.title,
                start_index=citation.start_index,
                end_index=citation.end_index,
                cited_text=citation.cited_text,
                published_at=citation.published_at,
                normalization_rule_version=normalization_rule_version,
            )
            for citation_ordinal, citation in enumerate(result.citations)
        ]
        self._session.add(response)
        return response

    def add_entity(self, response: AnalysisResponse, entity: ExtractedEntity) -> AnalysisEntity:
        mentions = list(entity.mentions)
        position = mention_position(response.response_text, mentions)
        if position is None:
            raise ValueError("persisted entities must contain at least one mention")
        model = AnalysisEntity(
            response=response,
            entity_key=entity.key,
            name=entity.name,
            kind=entity.kind,
            matched_aliases=list(dict.fromkeys(mention.alias for mention in mentions)),
            mention_count=len(mentions),
            first_mention_start=position.character_index,
            first_mention_relative=position.relative_position,
            position_bucket=position.bucket,
            mentions=[
                {
                    "alias": mention.alias,
                    "start": mention.start,
                    "end": mention.end,
                }
                for mention in mentions
            ],
            extraction_method=entity.extraction_method,
            extraction_rule_version=entity.rule_version,
        )
        self._session.add(model)
        return model

    def add_metric(
        self,
        analysis_run_id: UUID,
        metric: MetricResult,
    ) -> AnalysisScore:
        model = AnalysisScore(
            analysis_run_id=analysis_run_id,
            name=metric.name,
            numerator=metric.numerator,
            denominator=metric.denominator,
            value=metric.value,
            percentage=metric.percentage,
            is_defined=metric.is_defined,
            method="deterministic",
            rule_version=metric.rule_version,
            is_objective_truth=None,
            disclaimer=None,
        )
        self._session.add(model)
        return model

    def add_claim(
        self,
        *,
        response: AnalysisResponse,
        segment: ClaimSegment,
        assessment: ClaimAssessment,
        evidence: list[EvidenceMatch],
    ) -> AnalysisClaim:
        claim = AnalysisClaim(
            response=response,
            ordinal=segment.ordinal,
            claim_text=segment.text,
            start_index=segment.start,
            end_index=segment.end,
            classification=assessment.classification.value,
            confidence=assessment.confidence,
            explanation=assessment.explanation,
            classifier=assessment.classifier,
            model_identifier=assessment.model_identifier,
            segmentation_rule_version=segment.rule_version,
        )
        claim.evidence = [
            ClaimEvidence(
                source_type=match.candidate.source_type,
                source_id=UUID(match.candidate.source_id),
                source_reference=match.candidate.reference,
                url=match.candidate.url,
                excerpt=match.candidate.text,
                relevance_score=match.relevance_score,
                retrieval_rule_version=match.rule_version,
            )
            for match in evidence
        ]
        self._session.add(claim)
        return claim

    def add_risk_score(
        self,
        *,
        analysis_run_id: UUID,
        numerator: float,
        denominator: int,
        value: float | None,
        percentage: float | None,
        rule_version: str,
        disclaimer: str,
    ) -> AnalysisScore:
        model = AnalysisScore(
            analysis_run_id=analysis_run_id,
            name="claim_support_risk",
            numerator=numerator,
            denominator=denominator,
            value=value,
            percentage=percentage,
            is_defined=value is not None,
            method="model_assisted_aggregate",
            rule_version=rule_version,
            is_objective_truth=False,
            disclaimer=disclaimer,
        )
        self._session.add(model)
        return model

    async def get_run(self, analysis_id: UUID) -> AnalysisRun | None:
        return await self._session.get(AnalysisRun, analysis_id)

    async def list_citations(self, analysis_id: UUID) -> list[AnalysisCitation]:
        statement = (
            select(AnalysisCitation)
            .join(AnalysisResponse)
            .where(AnalysisResponse.analysis_run_id == analysis_id)
            .order_by(AnalysisResponse.ordinal, AnalysisCitation.ordinal)
        )
        return list((await self._session.scalars(statement)).all())

    async def list_entities(self, analysis_id: UUID) -> list[AnalysisEntity]:
        statement = (
            select(AnalysisEntity)
            .join(AnalysisResponse)
            .where(AnalysisResponse.analysis_run_id == analysis_id)
            .order_by(AnalysisResponse.ordinal, AnalysisEntity.first_mention_start)
        )
        return list((await self._session.scalars(statement)).all())

    async def list_scores(self, analysis_id: UUID) -> list[AnalysisScore]:
        statement = (
            select(AnalysisScore)
            .where(AnalysisScore.analysis_run_id == analysis_id)
            .order_by(AnalysisScore.name)
        )
        return list((await self._session.scalars(statement)).all())

    async def list_claims(self, analysis_id: UUID) -> list[AnalysisClaim]:
        statement = (
            select(AnalysisClaim)
            .join(AnalysisResponse)
            .where(AnalysisResponse.analysis_run_id == analysis_id)
            .options(selectinload(AnalysisClaim.evidence))
            .order_by(AnalysisResponse.ordinal, AnalysisClaim.ordinal)
        )
        return list((await self._session.scalars(statement)).all())

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from geolens_api.analysis.citations import (
    CITATION_RULE_VERSION,
    extract_normalized_domain,
)
from geolens_api.analysis.claims import (
    ClaimClassifier,
    ClaimSegment,
    EvidenceCandidate,
    EvidenceMatch,
    aggregate_claim_risk,
    chunk_evidence_text,
    rank_evidence,
    segment_factual_claims,
)
from geolens_api.analysis.entities import extract_entities
from geolens_api.analysis.matching import EntityRule
from geolens_api.analysis.metrics import (
    MetricResult,
    ResponseMeasurement,
    citation_share,
    entity_coverage,
    rank_weighted_share_of_ai_voice,
    target_domain_citation_coverage,
    visibility_rate,
)
from geolens_api.models.analysis_citation import AnalysisCitation
from geolens_api.models.analysis_claim import AnalysisClaim
from geolens_api.models.analysis_entity import AnalysisEntity
from geolens_api.models.analysis_response import AnalysisResponse
from geolens_api.models.analysis_run import AnalysisRun, AnalysisRunStatus
from geolens_api.models.analysis_score import AnalysisScore
from geolens_api.models.project import Project
from geolens_api.providers.contract import (
    Citation,
    Provider,
    ProviderError,
    ProviderResolver,
    ProviderResponse,
    ProviderResponseStatus,
    TokenUsage,
)
from geolens_api.providers.registry import ProviderModelMismatchError
from geolens_api.queues import AnalysisQueue
from geolens_api.repositories.analyses import AnalysisRepository
from geolens_api.schemas.analysis import (
    AnalysisStartRequest,
    AnalysisStartResponse,
    AnalysisStatus,
    PromptExecutionResponse,
    ProviderModelConfiguration,
)
from geolens_api.services.claim_classification import (
    ProviderClaimClassifier,
    UnconfiguredClaimClassifier,
)


class AnalysisProjectNotFoundError(LookupError):
    def __init__(self, project_id: UUID) -> None:
        super().__init__(f"Project {project_id} was not found")


class AnalysisCrawlNotFoundError(LookupError):
    def __init__(self, crawl_job_id: UUID) -> None:
        super().__init__(f"Crawl job {crawl_job_id} was not found")


class AnalysisCrawlProjectMismatchError(ValueError):
    def __init__(self, crawl_job_id: UUID, project_id: UUID) -> None:
        super().__init__(f"Crawl job {crawl_job_id} does not belong to project {project_id}")


class AnalysisNotFoundError(LookupError):
    def __init__(self, analysis_id: UUID) -> None:
        super().__init__(f"Analysis {analysis_id} was not found")


class AnalysisQueueUnavailableError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("The analysis could not be queued")


@dataclass
class _ClaimWork:
    response: AnalysisResponse
    segment: ClaimSegment
    evidence: list[EvidenceMatch]


class AnalysisService:
    """Queue and execute durable provider-neutral analysis runs."""

    def __init__(
        self,
        registry: ProviderResolver,
        session: AsyncSession | None = None,
        queue: AnalysisQueue | None = None,
    ) -> None:
        self._registry = registry
        self._session = session
        self._repository = AnalysisRepository(session) if session is not None else None
        self._queue = queue

    async def submit(self, data: AnalysisStartRequest) -> AnalysisStartResponse:
        providers = [self._registry.get(name) for name in data.providers]
        project = await self._project_context(data)
        classifier = (
            self._registry.get(data.claim_classifier_provider)
            if data.claim_classifier_provider is not None
            else None
        )
        run = await self._required_repository().create_run(
            project_id=project.id,
            crawl_job_id=data.crawl_job_id,
            provider_configurations=[
                self._provider_configuration(provider) for provider in providers
            ],
            prompts=data.prompts,
            claim_classifier_configuration=(
                self._provider_configuration(classifier) if classifier is not None else None
            ),
        )
        await self._required_session().commit()

        try:
            run.celery_task_id = await asyncio.to_thread(self._required_queue().enqueue, run.id)
        except Exception:
            run.status = AnalysisRunStatus.FAILED
            run.completed_at = datetime.now(timezone.utc)
            run.error_message = "The analysis could not be queued"
            await self._required_session().commit()
            raise AnalysisQueueUnavailableError from None
        await self._required_session().commit()
        return await self.get(run.id)

    async def execute(self, analysis_id: UUID) -> None:
        run = await self._required_repository().get_run(analysis_id)
        if run is None:
            raise AnalysisNotFoundError(analysis_id)
        if run.status not in {AnalysisRunStatus.PENDING, AnalysisRunStatus.RUNNING}:
            return

        try:
            providers = [
                self._resolve_configuration(configuration)
                for configuration in run.provider_configurations
            ]
            classifier = self._classifier_for_run(run)
            project = await self._required_repository().get_project(run.project_id)
            if project is None:
                raise AnalysisProjectNotFoundError(run.project_id)

            await self._required_repository().delete_artifacts(run.id)
            run.status = AnalysisRunStatus.RUNNING
            run.started_at = run.started_at or datetime.now(timezone.utc)
            run.completed_at = None
            run.error_message = None
            await self._required_session().commit()

            executions = [
                self._execute(provider, prompt) for provider in providers for prompt in run.prompts
            ]
            results = await asyncio.gather(*executions)
            analysis_status = self._analysis_status(results)
            await self._persist_analysis(
                run_id=run.id,
                project=project,
                crawl_job_id=run.crawl_job_id,
                results=results,
                classifier=classifier,
            )
            run.status = AnalysisRunStatus(analysis_status.value)
            run.completed_at = datetime.now(timezone.utc)
            await self._required_session().commit()
        except Exception as error:
            await self._mark_run_failed(run.id, error)
            raise

    async def get(self, analysis_id: UUID) -> AnalysisStartResponse:
        run = await self._required_repository().get_run(analysis_id)
        if run is None:
            raise AnalysisNotFoundError(analysis_id)
        await self._required_session().refresh(run)
        results = [
            self._prompt_execution_response(response)
            for response in await self._required_repository().list_responses(analysis_id)
        ]
        return AnalysisStartResponse(
            analysis_id=run.id,
            project_id=run.project_id,
            crawl_job_id=run.crawl_job_id,
            status=AnalysisStatus(run.status.value),
            started_at=run.started_at,
            completed_at=run.completed_at,
            error_message=run.error_message,
            celery_task_id=run.celery_task_id,
            provider_configurations=[
                ProviderModelConfiguration.model_validate(configuration)
                for configuration in run.provider_configurations
            ],
            prompts=run.prompts,
            claim_classifier_configuration=(
                ProviderModelConfiguration.model_validate(run.claim_classifier_configuration)
                if run.claim_classifier_configuration is not None
                else None
            ),
            results=results,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    async def _project_context(self, data: AnalysisStartRequest) -> Project:
        repository = self._required_repository()
        project = await repository.get_project(data.project_id)
        if project is None:
            raise AnalysisProjectNotFoundError(data.project_id)
        if data.crawl_job_id is not None:
            crawl_job = await repository.get_crawl_job(data.crawl_job_id)
            if crawl_job is None:
                raise AnalysisCrawlNotFoundError(data.crawl_job_id)
            if crawl_job.site.project_id != project.id:
                raise AnalysisCrawlProjectMismatchError(data.crawl_job_id, project.id)
        return project

    def _classifier_for_run(self, run: AnalysisRun) -> ClaimClassifier:
        if run.claim_classifier_configuration is None:
            return UnconfiguredClaimClassifier()
        return ProviderClaimClassifier(
            self._resolve_configuration(run.claim_classifier_configuration)
        )

    async def _persist_analysis(
        self,
        *,
        run_id: UUID,
        project: Project,
        crawl_job_id: UUID | None,
        results: list[PromptExecutionResponse],
        classifier: ClaimClassifier,
    ) -> None:
        repository = self._required_repository()
        rules = self._entity_rules(project)
        persisted_responses: list[AnalysisResponse] = []
        response_measurements: list[ResponseMeasurement] = []

        for ordinal, result in enumerate(results):
            domains = tuple(
                extract_normalized_domain(citation.url) for citation in result.citations
            )
            response = repository.add_response(
                analysis_run_id=run_id,
                ordinal=ordinal,
                result=result,
                normalization_rule_version=CITATION_RULE_VERSION,
                normalized_domains=domains,
            )
            persisted_responses.append(response)

        await self._required_session().flush()

        for result, response in zip(results, persisted_responses, strict=True):
            if result.status is not ProviderResponseStatus.SUCCEEDED:
                response_measurements.append(
                    ResponseMeasurement(
                        eligible=False,
                        target_mentioned=False,
                        entity_first_positions={},
                        citation_domains=(),
                    )
                )
                continue

            entities = extract_entities(result.response_text, rules)
            positions: dict[str, int] = {}
            for entity in entities:
                persisted_entity = repository.add_entity(response, entity)
                if entity.kind in {"target", "competitor"}:
                    positions[entity.key] = persisted_entity.first_mention_start
            response_measurements.append(
                ResponseMeasurement(
                    eligible=True,
                    target_mentioned="target" in positions,
                    entity_first_positions=positions,
                    citation_domains=tuple(
                        domain
                        for domain in (
                            extract_normalized_domain(citation.url) for citation in result.citations
                        )
                        if domain is not None
                    ),
                )
            )

        self._persist_deterministic_scores(
            run_id=run_id,
            project=project,
            measurements=response_measurements,
            rules=rules,
        )
        await self._required_session().flush()

        crawl_candidates = await self._crawl_evidence(crawl_job_id)
        claim_work = self._claim_work(
            persisted_responses,
            crawl_candidates,
        )
        # Provider/classifier I/O must never run while a database transaction is open.
        await self._required_session().commit()
        assessments = await asyncio.gather(
            *(classifier.classify(work.segment, work.evidence) for work in claim_work)
        )
        for work, assessment in zip(claim_work, assessments, strict=True):
            repository.add_claim(
                response=work.response,
                segment=work.segment,
                assessment=assessment,
                evidence=work.evidence,
            )

        classified_assessments = [
            assessment for assessment in assessments if assessment.classifier != "not_configured"
        ]
        risk = aggregate_claim_risk(classified_assessments)
        repository.add_risk_score(
            analysis_run_id=run_id,
            numerator=risk.numerator,
            denominator=risk.denominator,
            value=risk.value,
            percentage=risk.percentage,
            rule_version=risk.rule_version,
            disclaimer=risk.disclaimer,
        )

    async def _mark_run_failed(self, run_id: UUID, error: Exception) -> None:
        session = self._required_session()
        await session.rollback()
        run = await self._required_repository().get_run(run_id)
        if run is None:
            return
        run.status = AnalysisRunStatus.FAILED
        run.completed_at = datetime.now(timezone.utc)
        run.error_message = (
            str(error)
            if isinstance(error, ProviderModelMismatchError)
            else "Analysis processing failed"
        )
        await session.commit()

    def _persist_deterministic_scores(
        self,
        *,
        run_id: UUID,
        project: Project,
        measurements: list[ResponseMeasurement],
        rules: tuple[EntityRule, ...],
    ) -> None:
        repository = self._required_repository()
        target_domain = project.site.url if project.site is not None else None
        if target_domain is None:
            domain_metrics = (
                MetricResult(
                    name="target_domain_citation_coverage",
                    numerator=0,
                    denominator=0,
                    value=None,
                    percentage=None,
                ),
                MetricResult(
                    name="citation_share",
                    numerator=0,
                    denominator=0,
                    value=None,
                    percentage=None,
                ),
            )
        else:
            domain_metrics = (
                target_domain_citation_coverage(measurements, target_domain),
                citation_share(measurements, target_domain),
            )
        competitor_keys = tuple(rule.key for rule in rules if rule.kind == "competitor")
        tracked_keys = ("target", *competitor_keys)
        metrics = (
            visibility_rate(measurements),
            *domain_metrics,
            rank_weighted_share_of_ai_voice(
                measurements,
                target_entity_key="target",
                compared_entity_keys=competitor_keys,
            ),
            entity_coverage(measurements, tracked_entity_keys=tracked_keys),
        )
        for metric in metrics:
            repository.add_metric(run_id, metric)

    async def _crawl_evidence(self, crawl_job_id: UUID | None) -> list[EvidenceCandidate]:
        candidates: list[EvidenceCandidate] = []
        for page in await self._required_repository().list_crawl_pages(crawl_job_id):
            candidates.extend(
                chunk_evidence_text(
                    source_type="crawl_page",
                    source_id=str(page.id),
                    url=page.canonical_url or page.url,
                    text=page.main_text,
                )
            )
        return candidates

    @staticmethod
    def _claim_work(
        responses: list[AnalysisResponse],
        crawl_candidates: list[EvidenceCandidate],
    ) -> list[_ClaimWork]:
        work: list[_ClaimWork] = []
        for response in responses:
            if response.status != ProviderResponseStatus.SUCCEEDED.value:
                continue
            citation_candidates: list[EvidenceCandidate] = []
            for citation in response.citations:
                if citation.cited_text:
                    citation_candidates.extend(
                        chunk_evidence_text(
                            source_type="citation",
                            source_id=str(citation.id),
                            url=citation.url,
                            text=citation.cited_text,
                        )
                    )
            candidates = [*crawl_candidates, *citation_candidates]
            for segment in segment_factual_claims(response.response_text):
                work.append(
                    _ClaimWork(
                        response=response,
                        segment=segment,
                        evidence=rank_evidence(segment, candidates),
                    )
                )
        return work

    @staticmethod
    def _entity_rules(project: Project) -> tuple[EntityRule, ...]:
        target = EntityRule(
            key="target",
            name=project.name,
            aliases=tuple(project.aliases),
            kind="target",
        )
        competitors = tuple(
            EntityRule(
                key=f"competitor:{competitor.id}",
                name=competitor.name,
                aliases=tuple(competitor.aliases),
                kind="competitor",
            )
            for competitor in project.competitors
        )
        return (target, *competitors)

    @staticmethod
    async def _execute(provider: Provider, prompt: str) -> PromptExecutionResponse:
        try:
            result = await provider.execute(prompt)
        except Exception as error:
            result = ProviderResponse(
                provider=provider.name,
                model_identifier=provider.model_identifier,
                response_text="",
                raw_response={},
                latency_ms=0,
                status=ProviderResponseStatus.ERROR,
                error=ProviderError(
                    code="provider_execution_error",
                    message=str(error) or "Provider execution failed",
                    retryable=False,
                    attempts=1,
                ),
            )
        return PromptExecutionResponse(prompt=prompt, **result.model_dump())

    @staticmethod
    def _analysis_status(results: list[PromptExecutionResponse]) -> AnalysisStatus:
        success_count = sum(result.status is ProviderResponseStatus.SUCCEEDED for result in results)
        if success_count == len(results):
            return AnalysisStatus.SUCCEEDED
        if success_count:
            return AnalysisStatus.COMPLETED_WITH_ERRORS
        return AnalysisStatus.FAILED

    @staticmethod
    def _provider_configuration(provider: Provider) -> dict[str, str]:
        return {
            "name": provider.name,
            "model_identifier": provider.model_identifier,
        }

    def _resolve_configuration(self, value: dict[str, str]) -> Provider:
        configuration = ProviderModelConfiguration.model_validate(value)
        return self._registry.get_exact(configuration.name, configuration.model_identifier)

    @staticmethod
    def _prompt_execution_response(response: AnalysisResponse) -> PromptExecutionResponse:
        return PromptExecutionResponse(
            prompt=response.prompt,
            provider=response.provider,
            model_identifier=response.model_identifier,
            response_text=response.response_text,
            citations=[
                Citation(
                    url=citation.url,
                    title=citation.title,
                    start_index=citation.start_index,
                    end_index=citation.end_index,
                    cited_text=citation.cited_text,
                    published_at=citation.published_at,
                )
                for citation in sorted(response.citations, key=lambda item: item.ordinal)
            ],
            raw_response=response.raw_response,
            token_usage=TokenUsage.model_validate(response.token_usage),
            latency_ms=response.latency_ms,
            status=ProviderResponseStatus(response.status),
            error=(
                ProviderError.model_validate(response.error) if response.error is not None else None
            ),
        )

    def _required_repository(self) -> AnalysisRepository:
        if self._repository is None:
            raise RuntimeError("A database session is required for persisted analysis")
        return self._repository

    def _required_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("A database session is required for persisted analysis")
        return self._session

    def _required_queue(self) -> AnalysisQueue:
        if self._queue is None:
            raise RuntimeError("An analysis queue is required for submission")
        return self._queue


class AnalysisResultsService:
    """Read persisted analysis artifacts through one existence-checked boundary."""

    def __init__(self, session: AsyncSession) -> None:
        self._repository = AnalysisRepository(session)

    async def citations(self, analysis_id: UUID) -> list[AnalysisCitation]:
        await self._ensure_run(analysis_id)
        return await self._repository.list_citations(analysis_id)

    async def entities(self, analysis_id: UUID) -> list[AnalysisEntity]:
        await self._ensure_run(analysis_id)
        return await self._repository.list_entities(analysis_id)

    async def scores(self, analysis_id: UUID) -> list[AnalysisScore]:
        await self._ensure_run(analysis_id)
        return await self._repository.list_scores(analysis_id)

    async def claims(self, analysis_id: UUID) -> list[AnalysisClaim]:
        await self._ensure_run(analysis_id)
        return await self._repository.list_claims(analysis_id)

    async def _ensure_run(self, analysis_id: UUID) -> None:
        if await self._repository.get_run(analysis_id) is None:
            raise AnalysisNotFoundError(analysis_id)

from geolens_api.analysis.claims import (
    ClaimClassification,
    EvidenceCandidate,
    EvidenceMatch,
    segment_factual_claims,
)
from geolens_api.providers.contract import (
    ProviderError,
    ProviderResponse,
    ProviderResponseStatus,
)
from geolens_api.services.claim_classification import ProviderClaimClassifier


class RecordedClassifierProvider:
    name = "classifier"
    model_identifier = "classifier-v1"
    enabled = True
    disabled_reason = None

    def __init__(self, response_text: str, *, succeeds: bool = True) -> None:
        self.response_text = response_text
        self.succeeds = succeeds
        self.prompts: list[str] = []

    async def execute(self, prompt: str) -> ProviderResponse:
        self.prompts.append(prompt)
        if not self.succeeds:
            return ProviderResponse(
                provider=self.name,
                model_identifier=self.model_identifier,
                response_text="",
                latency_ms=1,
                status=ProviderResponseStatus.ERROR,
                error=ProviderError(
                    code="failed",
                    message="failed",
                    retryable=False,
                ),
            )
        return ProviderResponse(
            provider=self.name,
            model_identifier=self.model_identifier,
            response_text=self.response_text,
            latency_ms=1,
            status=ProviderResponseStatus.SUCCEEDED,
        )


async def test_provider_claim_classifier_parses_bounded_assessment() -> None:
    provider = RecordedClassifierProvider(
        'Result: {"classification":"supported","confidence":0.91,'
        '"explanation":"The evidence directly states the fact."}'
    )
    classifier = ProviderClaimClassifier(provider)
    claim = segment_factual_claims("Acme was founded in 2020.")[0]
    evidence = [
        EvidenceMatch(
            candidate=EvidenceCandidate(
                reference="crawl_page:1:chunk:0",
                source_type="crawl_page",
                source_id="1",
                url=None,
                text="Acme was founded in 2020.",
            ),
            relevance_score=1,
        )
    ]

    result = await classifier.classify(claim, evidence)

    assert result.classification is ClaimClassification.SUPPORTED
    assert result.confidence == 0.91
    assert result.classifier == "classifier"
    assert '"reference": "crawl_page:1:chunk:0"' in provider.prompts[0]


async def test_provider_claim_classifier_fails_closed_as_unverifiable() -> None:
    classifier = ProviderClaimClassifier(RecordedClassifierProvider("not json"))
    claim = segment_factual_claims("Acme was founded in 2020.")[0]
    evidence = [
        EvidenceMatch(
            candidate=EvidenceCandidate(
                reference="citation:1:chunk:0",
                source_type="citation",
                source_id="1",
                url=None,
                text="Acme was founded in 2020.",
            ),
            relevance_score=1,
        )
    ]

    result = await classifier.classify(claim, evidence)

    assert result.classification is ClaimClassification.UNVERIFIABLE
    assert result.confidence == 0
    assert "invalid" in result.explanation


async def test_provider_claim_classifier_does_not_invent_support_without_evidence() -> None:
    provider = RecordedClassifierProvider(
        '{"classification":"supported","confidence":1,"explanation":"Invented."}'
    )
    classifier = ProviderClaimClassifier(provider)
    claim = segment_factual_claims("Acme was founded in 2020.")[0]

    result = await classifier.classify(claim, [])

    assert result.classification is ClaimClassification.UNVERIFIABLE
    assert result.confidence == 0
    assert provider.prompts == []

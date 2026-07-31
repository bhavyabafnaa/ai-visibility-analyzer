import pytest

from geolens_api.analysis.claims import (
    ClaimAssessment,
    ClaimClassification,
    EvidenceCandidate,
    aggregate_claim_risk,
    chunk_evidence_text,
    rank_evidence,
    segment_factual_claims,
)


def test_factual_claim_segmentation_preserves_order_and_offsets() -> None:
    text = "Acme was founded in 2020. Is that recent? 2. Revenue reached $5 million;"

    claims = segment_factual_claims(text)

    assert [claim.text for claim in claims] == [
        "Acme was founded in 2020.",
        "Revenue reached $5 million;",
    ]
    assert [text[claim.start : claim.end] for claim in claims] == [
        "Acme was founded in 2020.",
        "Revenue reached $5 million;",
    ]
    assert [claim.ordinal for claim in claims] == [0, 1]


def test_evidence_chunking_is_bounded_and_references_are_stable() -> None:
    candidates = chunk_evidence_text(
        source_type="crawl_page",
        source_id="page-1",
        url="https://acme.test/about",
        text="Acme makes software. " * 20,
        max_characters=100,
    )

    assert len(candidates) > 1
    assert all(len(candidate.text) <= 100 for candidate in candidates)
    assert candidates[0].reference == "crawl_page:page-1:chunk:0"


def test_evidence_retrieval_ranks_relevant_database_chunks_first() -> None:
    claim = segment_factual_claims("Acme was founded in 2020.")[0]
    candidates = [
        EvidenceCandidate(
            reference="crawl_page:1:chunk:0",
            source_type="crawl_page",
            source_id="1",
            url="https://acme.test/about",
            text="Acme was founded in 2020 by Ada Example.",
        ),
        EvidenceCandidate(
            reference="citation:2:chunk:0",
            source_type="citation",
            source_id="2",
            url="https://other.test",
            text="Unrelated weather information for today.",
        ),
    ]

    matches = rank_evidence(claim, candidates)

    assert [match.candidate.reference for match in matches] == ["crawl_page:1:chunk:0"]
    assert matches[0].relevance_score == pytest.approx(0.88)


def test_claim_risk_formula_is_confidence_adjusted_and_non_objective() -> None:
    result = aggregate_claim_risk(
        [
            ClaimAssessment(
                classification=ClaimClassification.SUPPORTED,
                confidence=0.9,
                explanation="Evidence directly supports the claim.",
                classifier="test",
                model_identifier="test-v1",
            ),
            ClaimAssessment(
                classification=ClaimClassification.CONTRADICTED,
                confidence=0.8,
                explanation="Evidence states the opposite.",
                classifier="test",
                model_identifier="test-v1",
            ),
        ]
    )

    assert result.numerator == pytest.approx(0.98)
    assert result.denominator == 2
    assert result.value == pytest.approx(0.49)
    assert result.percentage == pytest.approx(49)
    assert result.is_objective_truth is False
    assert "not objective truth" in result.disclaimer


def test_claim_risk_is_undefined_without_claims() -> None:
    result = aggregate_claim_risk([])

    assert result.denominator == 0
    assert result.value is None
    assert result.is_objective_truth is False

import pytest

from geolens_api.analysis.metrics import (
    ResponseMeasurement,
    citation_share,
    entity_coverage,
    rank_weighted_share_of_ai_voice,
    target_domain_citation_coverage,
    visibility_rate,
)


def measurement(
    *,
    eligible: bool = True,
    target: bool = False,
    positions: dict[str, int] | None = None,
    domains: tuple[str, ...] = (),
) -> ResponseMeasurement:
    return ResponseMeasurement(
        eligible=eligible,
        target_mentioned=target,
        entity_first_positions=positions or {},
        citation_domains=domains,
    )


def test_visibility_rate_formula_excludes_ineligible_responses() -> None:
    result = visibility_rate(
        [
            measurement(target=True),
            measurement(target=False),
            measurement(eligible=False, target=True),
        ]
    )

    assert result.numerator == 1
    assert result.denominator == 2
    assert result.value == 0.5
    assert result.percentage == 50


def test_visibility_rate_is_explicitly_undefined_for_empty_denominator() -> None:
    result = visibility_rate([measurement(eligible=False, target=True)])

    assert result.numerator == 0
    assert result.denominator == 0
    assert result.value is None
    assert result.percentage is None
    assert result.is_defined is False


def test_target_domain_citation_coverage_formula() -> None:
    result = target_domain_citation_coverage(
        [
            measurement(target=True, domains=("docs.acme.test",)),
            measurement(target=True, domains=("other.test",)),
            measurement(target=False, domains=("acme.test",)),
        ],
        "acme.test",
    )

    assert result.numerator == 1
    assert result.denominator == 2
    assert result.value == 0.5


def test_target_domain_citation_coverage_is_undefined_without_mentions() -> None:
    result = target_domain_citation_coverage(
        [measurement(target=False, domains=("acme.test",))],
        "acme.test",
    )

    assert result.denominator == 0
    assert result.value is None


def test_citation_share_deduplicates_each_domain_within_a_response() -> None:
    result = citation_share(
        [
            measurement(domains=("acme.test", "acme.test", "other.test")),
            measurement(domains=("docs.acme.test",)),
        ],
        "acme.test",
    )

    assert result.numerator == 2
    assert result.denominator == 3
    assert result.value == pytest.approx(2 / 3)


def test_citation_share_is_undefined_without_normalized_citations() -> None:
    result = citation_share([measurement()], "acme.test")

    assert result.denominator == 0
    assert result.value is None


def test_rank_weighted_share_of_ai_voice_uses_reciprocal_first_mention_rank() -> None:
    result = rank_weighted_share_of_ai_voice(
        [
            measurement(target=True, positions={"competitor": 0, "target": 10}),
            measurement(target=True, positions={"target": 0}),
        ],
        target_entity_key="target",
        compared_entity_keys=("competitor",),
    )

    assert result.numerator == 1.5
    assert result.denominator == 2.5
    assert result.value == 0.6


def test_rank_weighted_share_is_undefined_without_compared_mentions() -> None:
    result = rank_weighted_share_of_ai_voice(
        [measurement()],
        target_entity_key="target",
        compared_entity_keys=("competitor",),
    )

    assert result.value is None


def test_entity_coverage_formula_counts_response_entity_pairs() -> None:
    result = entity_coverage(
        [
            measurement(positions={"target": 1, "competitor": 5}),
            measurement(positions={"target": 2}),
            measurement(eligible=False, positions={"competitor": 0}),
        ],
        tracked_entity_keys=("target", "competitor"),
    )

    assert result.numerator == 3
    assert result.denominator == 4
    assert result.value == 0.75


def test_entity_coverage_is_undefined_for_an_empty_tracked_set() -> None:
    result = entity_coverage([measurement()], tracked_entity_keys=())

    assert result.value is None

from dataclasses import dataclass

from geolens_api.analysis.citations import domain_matches

METRIC_RULE_VERSION = "metrics-v1"


@dataclass(frozen=True)
class ResponseMeasurement:
    eligible: bool
    target_mentioned: bool
    entity_first_positions: dict[str, int]
    citation_domains: tuple[str, ...]


@dataclass(frozen=True)
class MetricResult:
    name: str
    numerator: float
    denominator: float
    value: float | None
    percentage: float | None
    rule_version: str = METRIC_RULE_VERSION

    @property
    def is_defined(self) -> bool:
        return self.value is not None


def visibility_rate(responses: list[ResponseMeasurement]) -> MetricResult:
    """Eligible responses mentioning the target / eligible responses."""

    eligible = [response for response in responses if response.eligible]
    numerator = sum(response.target_mentioned for response in eligible)
    return _ratio("visibility_rate", numerator, len(eligible))


def target_domain_citation_coverage(
    responses: list[ResponseMeasurement],
    target_domain: str,
) -> MetricResult:
    """Target-mention responses citing target / target-mention responses."""

    mentioned = [
        response for response in responses if response.eligible and response.target_mentioned
    ]
    numerator = sum(
        any(domain_matches(domain, target_domain) for domain in response.citation_domains)
        for response in mentioned
    )
    return _ratio("target_domain_citation_coverage", numerator, len(mentioned))


def citation_share(
    responses: list[ResponseMeasurement],
    target_domain: str,
) -> MetricResult:
    """Target-domain response/domain occurrences / all response/domain occurrences."""

    normalized_domain_sets = [
        set(response.citation_domains) for response in responses if response.eligible
    ]
    denominator = sum(len(domains) for domains in normalized_domain_sets)
    numerator = sum(
        sum(domain_matches(domain, target_domain) for domain in domains)
        for domains in normalized_domain_sets
    )
    return _ratio("citation_share", numerator, denominator)


def rank_weighted_share_of_ai_voice(
    responses: list[ResponseMeasurement],
    *,
    target_entity_key: str,
    compared_entity_keys: tuple[str, ...],
) -> MetricResult:
    """Target reciprocal-rank weight / reciprocal-rank weight for compared entities."""

    comparison_set = set(compared_entity_keys)
    comparison_set.add(target_entity_key)
    numerator = 0.0
    denominator = 0.0
    for response in responses:
        if not response.eligible:
            continue
        ranked = sorted(
            (
                (position, entity_key)
                for entity_key, position in response.entity_first_positions.items()
                if entity_key in comparison_set
            ),
            key=lambda item: (item[0], item[1]),
        )
        for rank, (_, entity_key) in enumerate(ranked, start=1):
            weight = 1 / rank
            denominator += weight
            if entity_key == target_entity_key:
                numerator += weight
    return _ratio("rank_weighted_share_of_ai_voice", numerator, denominator)


def entity_coverage(
    responses: list[ResponseMeasurement],
    *,
    tracked_entity_keys: tuple[str, ...],
) -> MetricResult:
    """Observed eligible response/entity pairs / possible response/entity pairs."""

    eligible = [response for response in responses if response.eligible]
    tracked = set(tracked_entity_keys)
    denominator = len(eligible) * len(tracked)
    numerator = sum(
        len(set(response.entity_first_positions).intersection(tracked)) for response in eligible
    )
    return _ratio("entity_coverage", numerator, denominator)


def _ratio(name: str, numerator: float, denominator: float) -> MetricResult:
    value = numerator / denominator if denominator else None
    return MetricResult(
        name=name,
        numerator=float(numerator),
        denominator=float(denominator),
        value=value,
        percentage=value * 100 if value is not None else None,
    )

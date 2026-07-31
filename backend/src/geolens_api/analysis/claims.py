import math
import re
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

CLAIM_RULE_VERSION = "claim-segmentation-v1"
EVIDENCE_RULE_VERSION = "evidence-retrieval-v1"
RISK_RULE_VERSION = "claim-risk-v1"
RISK_DISCLAIMER = (
    "This model-assisted claim-support risk estimate is not objective truth; "
    "it depends on available evidence and classifier judgment."
)

_SEGMENT_PATTERN = re.compile(r"[^.!?;\n]+(?:[.!?;]+|$)")
_TOKEN_PATTERN = re.compile(r"[\w]+", re.UNICODE)
_LEADING_LIST_MARKER = re.compile(r"^(?:[-*•]\s+|\d+[.)]\s+)")
_NON_FACTUAL_PREFIXES = (
    "i think ",
    "i believe ",
    "in my opinion ",
    "consider ",
    "try ",
)
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}


class ClaimClassification(str, Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True)
class ClaimSegment:
    ordinal: int
    text: str
    start: int
    end: int
    rule_version: str = CLAIM_RULE_VERSION


@dataclass(frozen=True)
class EvidenceCandidate:
    reference: str
    source_type: str
    source_id: str
    url: str | None
    text: str


@dataclass(frozen=True)
class EvidenceMatch:
    candidate: EvidenceCandidate
    relevance_score: float
    rule_version: str = EVIDENCE_RULE_VERSION


@dataclass(frozen=True)
class ClaimAssessment:
    classification: ClaimClassification
    confidence: float
    explanation: str
    classifier: str
    model_identifier: str | None

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("claim confidence must be between 0 and 1")
        if not self.explanation.strip():
            raise ValueError("claim explanation cannot be blank")


class ClaimClassifier(Protocol):
    """Model-assistance boundary; deterministic analysis never implements this protocol."""

    async def classify(
        self,
        claim: ClaimSegment,
        evidence: list[EvidenceMatch],
    ) -> ClaimAssessment: ...


@dataclass(frozen=True)
class ClaimRiskResult:
    numerator: float
    denominator: int
    value: float | None
    percentage: float | None
    is_objective_truth: bool = False
    disclaimer: str = RISK_DISCLAIMER
    rule_version: str = RISK_RULE_VERSION


def segment_factual_claims(response_text: str) -> list[ClaimSegment]:
    """Segment declarative sentence/semicolon units with stable source offsets."""

    claims: list[ClaimSegment] = []
    for match in _SEGMENT_PATTERN.finditer(response_text):
        raw = match.group(0)
        leading = len(raw) - len(raw.lstrip())
        trailing = len(raw) - len(raw.rstrip())
        text = raw.strip()
        marker = _LEADING_LIST_MARKER.match(text)
        if marker is not None:
            leading += marker.end()
            text = text[marker.end() :].lstrip()
        if not _is_factual_candidate(text):
            continue
        start = match.start() + leading
        end = match.end() - trailing
        claims.append(
            ClaimSegment(
                ordinal=len(claims),
                text=text,
                start=start,
                end=end,
            )
        )
    return claims


def chunk_evidence_text(
    *,
    source_type: str,
    source_id: str,
    url: str | None,
    text: str,
    max_characters: int = 800,
) -> list[EvidenceCandidate]:
    """Split database evidence into bounded, stable sentence-group chunks."""

    if max_characters < 100:
        raise ValueError("max_characters must be at least 100")
    units = [match.group(0).strip() for match in _SEGMENT_PATTERN.finditer(text)]
    units = [unit for unit in units if unit]
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    for unit in units:
        if len(unit) > max_characters:
            if current:
                chunks.append(" ".join(current))
                current = []
                current_length = 0
            chunks.extend(_split_long_unit(unit, max_characters))
            continue
        projected = current_length + (1 if current else 0) + len(unit)
        if current and projected > max_characters:
            chunks.append(" ".join(current))
            current = [unit]
            current_length = len(unit)
        else:
            current.append(unit)
            current_length = projected
    if current:
        chunks.append(" ".join(current))
    if not chunks and text.strip():
        chunks = _split_long_unit(text.strip(), max_characters)

    return [
        EvidenceCandidate(
            reference=f"{source_type}:{source_id}:chunk:{index}",
            source_type=source_type,
            source_id=source_id,
            url=url,
            text=chunk,
        )
        for index, chunk in enumerate(chunks)
    ]


def rank_evidence(
    claim: ClaimSegment,
    candidates: list[EvidenceCandidate],
    *,
    limit: int = 5,
    minimum_score: float = 0.05,
) -> list[EvidenceMatch]:
    """Rank evidence by deterministic IDF-weighted claim-token coverage and Jaccard."""

    if limit < 1:
        raise ValueError("limit must be positive")
    query_tokens = set(_tokens(claim.text))
    if not query_tokens or not candidates:
        return []

    candidate_tokens = [set(_tokens(candidate.text)) for candidate in candidates]
    document_frequency: Counter[str] = Counter()
    for tokens in candidate_tokens:
        document_frequency.update(tokens)
    document_count = len(candidates)

    query_weights = {
        token: math.log((1 + document_count) / (1 + document_frequency[token])) + 1
        for token in query_tokens
    }
    total_query_weight = sum(query_weights.values())
    ranked: list[EvidenceMatch] = []
    for candidate, tokens in zip(candidates, candidate_tokens, strict=True):
        overlap = query_tokens.intersection(tokens)
        if not overlap:
            continue
        weighted_coverage = sum(query_weights[token] for token in overlap) / total_query_weight
        jaccard = len(overlap) / len(query_tokens.union(tokens))
        score = 0.7 * weighted_coverage + 0.3 * jaccard
        if score >= minimum_score:
            ranked.append(EvidenceMatch(candidate=candidate, relevance_score=score))
    return sorted(
        ranked,
        key=lambda item: (-item.relevance_score, item.candidate.reference),
    )[:limit]


def aggregate_claim_risk(assessments: list[ClaimAssessment]) -> ClaimRiskResult:
    """Aggregate confidence-adjusted label weights without presenting truth probability."""

    base_risk = {
        ClaimClassification.SUPPORTED: 0.0,
        ClaimClassification.PARTIALLY_SUPPORTED: 0.4,
        ClaimClassification.UNSUPPORTED: 0.8,
        ClaimClassification.CONTRADICTED: 1.0,
        ClaimClassification.UNVERIFIABLE: 0.6,
    }
    contributions = [
        assessment.confidence * base_risk[assessment.classification]
        + (1 - assessment.confidence) * base_risk[ClaimClassification.UNVERIFIABLE]
        for assessment in assessments
    ]
    numerator = sum(contributions)
    value = numerator / len(contributions) if contributions else None
    return ClaimRiskResult(
        numerator=numerator,
        denominator=len(contributions),
        value=value,
        percentage=value * 100 if value is not None else None,
    )


def _is_factual_candidate(value: str) -> bool:
    if not value or value.endswith("?"):
        return False
    words = _TOKEN_PATTERN.findall(value)
    if len(words) < 3:
        return False
    lowered = value.casefold()
    return not lowered.startswith(_NON_FACTUAL_PREFIXES)


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in (match.group(0).casefold() for match in _TOKEN_PATTERN.finditer(value))
        if token not in _STOP_WORDS and len(token) > 1
    ]


def _split_long_unit(value: str, maximum: int) -> list[str]:
    chunks: list[str] = []
    remaining = value
    while len(remaining) > maximum:
        split_at = remaining.rfind(" ", 0, maximum + 1)
        if split_at <= 0:
            split_at = maximum
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks

import re
from dataclasses import dataclass
from hashlib import sha256

from geolens_api.analysis.matching import EntityRule, MentionMatch, find_entity_mentions

ENTITY_RULE_VERSION = "entity-v1"

_ENTITY_PATTERN = re.compile(
    r"(?<![\w])"
    r"(?:[A-Z][\w'’-]*|[A-Z]{2,})"
    r"(?:\s+(?:(?:of|the|and|for)\s+)?(?:[A-Z][\w'’-]*|[A-Z]{2,}))*"
)
_GENERIC_SINGLE_WORDS = {
    "A",
    "An",
    "And",
    "But",
    "For",
    "However",
    "In",
    "It",
    "No",
    "The",
    "This",
    "That",
    "These",
    "Those",
    "Yes",
}


@dataclass(frozen=True)
class ExtractedEntity:
    key: str
    name: str
    kind: str
    mentions: tuple[MentionMatch, ...]
    extraction_method: str
    rule_version: str = ENTITY_RULE_VERSION


def extract_entities(
    text: str,
    tracked_rules: tuple[EntityRule, ...] = (),
) -> list[ExtractedEntity]:
    """Extract configured entities plus deterministic capitalized-name candidates."""

    tracked_mentions = find_entity_mentions(text, tracked_rules)
    grouped: dict[str, list[MentionMatch]] = {}
    rules_by_key = {rule.key: rule for rule in tracked_rules}
    for mention in tracked_mentions:
        grouped.setdefault(mention.entity_key, []).append(mention)

    entities = [
        ExtractedEntity(
            key=key,
            name=rules_by_key[key].name,
            kind=rules_by_key[key].kind,
            mentions=tuple(mentions),
            extraction_method="configured_alias",
        )
        for key, mentions in grouped.items()
    ]

    occupied = [(mention.start, mention.end) for mention in tracked_mentions]
    candidates: dict[str, tuple[str, list[MentionMatch]]] = {}
    for candidate in _ENTITY_PATTERN.finditer(text):
        name = candidate.group(0).strip()
        if name in _GENERIC_SINGLE_WORDS:
            continue
        if any(candidate.start() < end and candidate.end() > start for start, end in occupied):
            continue
        key = f"extracted:{_entity_key(name)}"
        mention = MentionMatch(
            entity_key=key,
            entity_name=name,
            entity_kind="extracted",
            alias=name,
            start=candidate.start(),
            end=candidate.end(),
        )
        canonical_name, mentions = candidates.setdefault(key, (name, []))
        if len(name) > len(canonical_name):
            candidates[key] = (name, mentions)
        mentions.append(mention)

    entities.extend(
        ExtractedEntity(
            key=key,
            name=name,
            kind="extracted",
            mentions=tuple(mentions),
            extraction_method="capitalized_phrase",
        )
        for key, (name, mentions) in candidates.items()
    )
    return sorted(
        entities,
        key=lambda entity: (
            min(mention.start for mention in entity.mentions),
            entity.key,
        ),
    )


def _entity_key(value: str) -> str:
    slug = "-".join(re.findall(r"\w+", value.casefold()))
    if len(slug) <= 220:
        return slug
    digest = sha256(slug.encode("utf-8")).hexdigest()[:12]
    return f"{slug[:207]}-{digest}"

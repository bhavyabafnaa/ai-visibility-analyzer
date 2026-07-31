from dataclasses import dataclass
from unicodedata import normalize

MATCHING_RULE_VERSION = "mention-v1"


@dataclass(frozen=True)
class EntityRule:
    """A canonical entity and the explicit aliases allowed to match it."""

    key: str
    name: str
    aliases: tuple[str, ...] = ()
    kind: str = "tracked"

    def terms(self) -> tuple[str, ...]:
        seen: set[str] = set()
        terms: list[str] = []
        for term in (self.name, *self.aliases):
            canonical, _ = _normal_form(term)
            if canonical and canonical not in seen:
                seen.add(canonical)
                terms.append(term)
        return tuple(terms)


@dataclass(frozen=True)
class MentionMatch:
    entity_key: str
    entity_name: str
    entity_kind: str
    alias: str
    start: int
    end: int


@dataclass(frozen=True)
class MentionPosition:
    """Position of an entity's first mention in one response."""

    character_index: int
    relative_position: float
    bucket: str
    rule_version: str = MATCHING_RULE_VERSION


def find_entity_mentions(text: str, rules: tuple[EntityRule, ...]) -> list[MentionMatch]:
    """Match configured names/aliases using Unicode-aware whole-term boundaries."""

    normalized_text, source_indexes = _normal_form(text)
    if not normalized_text:
        return []

    matches_by_identity: dict[tuple[str, int, int], MentionMatch] = {}
    for rule in rules:
        for alias in rule.terms():
            normalized_alias, _ = _normal_form(alias)
            if not normalized_alias:
                continue
            search_from = 0
            while True:
                position = normalized_text.find(normalized_alias, search_from)
                if position < 0:
                    break
                search_from = position + 1
                end_position = position + len(normalized_alias)
                if not _has_term_boundaries(normalized_text, position, end_position):
                    continue
                start = source_indexes[position]
                end = source_indexes[end_position - 1] + 1
                identity = (rule.key, start, end)
                candidate = MentionMatch(
                    entity_key=rule.key,
                    entity_name=rule.name,
                    entity_kind=rule.kind,
                    alias=alias,
                    start=start,
                    end=end,
                )
                current = matches_by_identity.get(identity)
                if current is None or len(alias) > len(current.alias):
                    matches_by_identity[identity] = candidate

    ordered = sorted(
        matches_by_identity.values(),
        key=lambda match: (match.start, -(match.end - match.start), match.entity_key),
    )
    non_overlapping: list[MentionMatch] = []
    for candidate in ordered:
        if any(
            candidate.entity_key == accepted.entity_key
            and candidate.start < accepted.end
            and candidate.end > accepted.start
            for accepted in non_overlapping
        ):
            continue
        non_overlapping.append(candidate)
    return non_overlapping


def mention_position(text: str, matches: list[MentionMatch]) -> MentionPosition | None:
    """Return first-character position divided by response character length."""

    if not matches:
        return None
    first_index = min(match.start for match in matches)
    relative = first_index / max(len(text), 1)
    if relative < 1 / 3:
        bucket = "early"
    elif relative < 2 / 3:
        bucket = "middle"
    else:
        bucket = "late"
    return MentionPosition(
        character_index=first_index,
        relative_position=relative,
        bucket=bucket,
    )


def _normal_form(value: str) -> tuple[str, list[int]]:
    """Normalize case and separators while retaining indexes into the source."""

    characters: list[str] = []
    indexes: list[int] = []
    separator_pending = False
    separator_index = 0
    for source_index, source_character in enumerate(value):
        expanded = normalize("NFKC", source_character).casefold()
        for character in expanded:
            if character.isalnum() or character in {"+", "#", "&"}:
                if separator_pending and characters:
                    characters.append(" ")
                    indexes.append(separator_index)
                separator_pending = False
                characters.append(character)
                indexes.append(source_index)
            else:
                if not separator_pending:
                    separator_index = source_index
                separator_pending = True
    return "".join(characters), indexes


def _has_term_boundaries(value: str, start: int, end: int) -> bool:
    return (start == 0 or value[start - 1] == " ") and (end == len(value) or value[end] == " ")

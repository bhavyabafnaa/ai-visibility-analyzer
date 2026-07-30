import pytest

from geolens_api.analysis.matching import (
    EntityRule,
    find_entity_mentions,
    mention_position,
)


def test_brand_alias_and_competitor_matching_is_case_and_separator_insensitive() -> None:
    rules = (
        EntityRule(key="target", name="Acme Cloud", aliases=("ACME",), kind="target"),
        EntityRule(
            key="competitor:globex",
            name="Globex AI",
            aliases=("Globex",),
            kind="competitor",
        ),
    )

    matches = find_entity_mentions(
        "ACME-Cloud leads Acme, while globex competes.",
        rules,
    )

    assert [(match.entity_key, match.alias, match.start, match.end) for match in matches] == [
        ("target", "Acme Cloud", 0, 10),
        ("target", "ACME", 17, 21),
        ("competitor:globex", "Globex", 29, 35),
    ]


def test_alias_matching_uses_whole_term_boundaries() -> None:
    rule = EntityRule(key="target", name="Art")

    matches = find_entity_mentions("Cart is not Art.", (rule,))

    assert [(match.start, match.end) for match in matches] == [(12, 15)]


def test_mention_position_formula_and_bucket_are_deterministic() -> None:
    text = "0123456789 Acme is visible."
    matches = find_entity_mentions(text, (EntityRule(key="target", name="Acme"),))

    position = mention_position(text, matches)

    assert position is not None
    assert position.character_index == 11
    assert position.relative_position == pytest.approx(11 / len(text))
    assert position.bucket == "middle"


def test_mention_position_is_undefined_without_a_match() -> None:
    assert mention_position("No tracked brand.", []) is None

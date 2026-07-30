from geolens_api.analysis.entities import extract_entities
from geolens_api.analysis.matching import EntityRule


def test_entity_extraction_combines_configured_and_capitalized_entities() -> None:
    entities = extract_entities(
        "Acme works with Northwind Labs. ACME is growing.",
        (EntityRule(key="target", name="Acme", aliases=("ACME",), kind="target"),),
    )

    assert [(entity.key, entity.name, entity.extraction_method) for entity in entities] == [
        ("target", "Acme", "configured_alias"),
        ("extracted:northwind-labs", "Northwind Labs", "capitalized_phrase"),
    ]
    assert len(entities[0].mentions) == 2


def test_entity_extraction_does_not_duplicate_tracked_spans() -> None:
    entities = extract_entities(
        "Northwind Labs provides analytics.",
        (
            EntityRule(
                key="competitor:northwind",
                name="Northwind Labs",
                kind="competitor",
            ),
        ),
    )

    assert len(entities) == 1
    assert entities[0].key == "competitor:northwind"

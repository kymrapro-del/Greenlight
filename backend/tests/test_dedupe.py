"""Phase 3 — canonicalisation.

Phase entièrement déterministe : ces tests tranchent le comportement, il n'y a
pas de « ça dépend du modèle ». Chaque fusion évitée est une recherche Parallel
économisée ; chaque fusion abusive serait un risque masqué.
"""

from __future__ import annotations

from greenlight.agents.dedupe import canonicalize, entity_id, normalize_name
from greenlight.agents.extract import SceneEntities
from greenlight.models import ContextTier, EntityType, ExtractedEntity, Scene


def scene(number: int) -> Scene:
    return Scene(id=f"d1-s{number}", number=number, heading=f"INT. LOCATION {number} - NIGHT")


def bundle(number: int, *entities: ExtractedEntity) -> SceneEntities:
    return SceneEntities(scene=scene(number), entities=list(entities))


def ent(
    name: str,
    etype: EntityType = EntityType.CHARACTER_NAME,
    tier: ContextTier = ContextTier.NEUTRAL,
) -> ExtractedEntity:
    return ExtractedEntity(name=name, type=etype, context_tier=tier, quote=name)


# --- Normalisation --------------------------------------------------------


def test_honorifics_and_articles_are_stripped():
    assert normalize_name("Dr. Marcus Webb") == "marcus webb"
    assert normalize_name("THE Black Cat Tavern") == "black cat tavern"
    assert normalize_name("  Detective  Reyes ") == "reyes"


def test_ids_are_stable_across_writings():
    a = entity_id(EntityType.BUSINESS, "The Black Cat Tavern")
    b = entity_id(EntityType.BUSINESS, "the black cat tavern")
    assert a == b == "business:black-cat-tavern"


# --- Fusion ---------------------------------------------------------------


def test_same_entity_written_three_ways_becomes_one():
    entities = canonicalize(
        [
            bundle(1, ent("THE BLACK CAT TAVERN", EntityType.BUSINESS)),
            bundle(2, ent("the Black Cat Tavern", EntityType.BUSINESS)),
            bundle(4, ent("The Black Cat Tavern", EntityType.BUSINESS)),
        ]
    )
    assert len(entities) == 1
    assert entities[0].canonical_name == "The Black Cat Tavern"
    assert len(entities[0].occurrences) == 3


def test_surname_joins_its_full_name():
    entities = canonicalize(
        [
            bundle(1, ent("Dr. Marcus Webb")),
            bundle(2, ent("WEBB")),
        ]
    )
    assert len(entities) == 1
    assert entities[0].canonical_name == "Dr. Marcus Webb"
    assert "WEBB" in entities[0].aliases


def test_ambiguous_surname_refuses_to_merge():
    """Deux Webb dans le scénario : fusionner masquerait un vrai risque."""
    entities = canonicalize(
        [
            bundle(1, ent("Marcus Webb")),
            bundle(2, ent("Sarah Webb")),
            bundle(3, ent("WEBB")),
        ]
    )
    assert len(entities) == 3


def test_surname_rule_does_not_apply_to_places():
    """« Tavern » n'est pas « The Black Cat Tavern »."""
    entities = canonicalize(
        [
            bundle(1, ent("The Black Cat Tavern", EntityType.BUSINESS)),
            bundle(2, ent("Tavern", EntityType.BUSINESS)),
        ]
    )
    assert len(entities) == 2


def test_same_name_different_types_stay_separate():
    entities = canonicalize(
        [
            bundle(1, ent("Mercy", EntityType.CHARACTER_NAME)),
            bundle(2, ent("Mercy", EntityType.INSTITUTION)),
        ]
    )
    assert len(entities) == 2


# --- Contexte -------------------------------------------------------------


def test_worst_depiction_across_scenes_wins():
    """Une seule scène délictueuse suffit à exposer : c'est le pire contexte,
    pas le plus fréquent, qui pilote le verdict."""
    entities = canonicalize(
        [
            bundle(1, ent("The Black Cat Tavern", EntityType.BUSINESS, ContextTier.NEUTRAL)),
            bundle(2, ent("The Black Cat Tavern", EntityType.BUSINESS, ContextTier.NEUTRAL)),
            bundle(4, ent("The Black Cat Tavern", EntityType.BUSINESS, ContextTier.ILLEGAL)),
        ]
    )
    assert entities[0].worst_context is ContextTier.ILLEGAL


def test_occurrences_keep_their_scene_numbers():
    entities = canonicalize(
        [
            bundle(3, ent("Coca-Cola", EntityType.PRODUCT_BRAND)),
            bundle(7, ent("Coca-Cola", EntityType.PRODUCT_BRAND)),
        ]
    )
    assert sorted(o.scene_number for o in entities[0].occurrences) == [3, 7]


# --- Ordre et robustesse --------------------------------------------------


def test_most_recurrent_entities_come_first():
    entities = canonicalize(
        [
            bundle(1, ent("Daniel Reyes"), ent("Marcus Webb")),
            bundle(2, ent("Daniel Reyes")),
        ]
    )
    assert entities[0].canonical_name == "Daniel Reyes"


def test_empty_and_punctuation_only_names_are_ignored():
    entities = canonicalize([bundle(1, ent("---"), ent("Daniel Reyes"))])
    assert [e.canonical_name for e in entities] == ["Daniel Reyes"]


def test_no_extraction_yields_no_entity():
    assert canonicalize([bundle(1)]) == []

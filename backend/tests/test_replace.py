"""Phase 6 — remplacements re-vérifiés.

Le point testé n'est pas la qualité des noms proposés, c'est la discipline : ne
déclarer vérifié que ce qui est repassé par la recherche sans résultat, ne rien
proposer là où renommer ne règle rien, et ne rien payer là où la convention
professionnelle donne déjà la réponse.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from greenlight.agents.gemini import GeminiClient
from greenlight.agents.replace import (
    conventional_replacement,
    suggest_replacement,
    suggest_replacements,
)
from greenlight.models import ContextTier, Entity, EntityType, Finding, Occurrence, Verdict
from greenlight.tools.parallel_search import ParallelSearch, SearchResponse, SearchResult


def make(name: str, etype: EntityType, tier: ContextTier = ContextTier.ILLEGAL) -> Entity:
    return Entity(
        id=f"{etype.value.lower()}:{name.lower().replace(' ', '-')}",
        canonical_name=name,
        type=etype,
        occurrences=[
            Occurrence(scene_id="s1", scene_number=1, context_tier=tier, quote=f"{name} appears.")
        ],
    )


def finding_for(entity: Entity, verdict: Verdict = Verdict.CHANGE_RECOMMENDED) -> Finding:
    return Finding(
        id=f"d1:{entity.id}",
        entity_id=entity.id,
        draft_id="d1",
        verdict=verdict,
        confidence=0.9,
        rationale="Entité réelle mise en cause par la scène.",
        context_tier=entity.worst_context,
    )


def client_proposing(*names: str) -> GeminiClient:
    client = GeminiClient(
        transport=lambda _: {"json": json.dumps({"candidates": list(names)}), "usage": {}}
    )
    client._fixtures.mode = "live"
    return client


class SearchFinding(ParallelSearch):
    """Rend des résultats pour les noms listés, rien pour les autres."""

    def __init__(self, real_names: tuple[str, ...] = (), fail: bool = False) -> None:
        super().__init__()
        self.real_names = real_names
        self.fail = fail
        self.probed: list[str] = []

    def search(self, objective, search_queries, mode=None):  # type: ignore[override]
        self.probed.append(search_queries[0])
        if self.fail:
            raise RuntimeError("recherche indisponible")
        hit = any(name.lower() in objective.lower() for name in self.real_names)
        return SearchResponse(
            search_id="s",
            results=[SearchResult(url="https://real.test/x")] if hit else [],
            mode=mode or "fast",
        )


# --- Ce que la convention tranche : gratuit et sûr par construction -------


def test_phone_is_moved_into_the_fictional_range():
    assert conventional_replacement(make("312-555-8890", EntityType.PHONE)) == "312-555-0190"


def test_phone_replacement_keeps_the_area_code():
    """La réplique doit sonner pareil une fois le numéro changé."""
    assert conventional_replacement(make("(212) 555-8890", EntityType.PHONE)).startswith("212-")


def test_email_moves_to_a_reserved_domain():
    assert conventional_replacement(make("d@corp.test", EntityType.URL_EMAIL)) == "d@example.com"


def test_no_convention_for_a_business_name():
    assert conventional_replacement(make("The Black Cat Tavern", EntityType.BUSINESS)) is None


def test_conventional_replacement_costs_neither_model_nor_search():
    def must_not_be_called(_: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("le modèle a été appelé pour une réponse conventionnelle")

    client = GeminiClient(transport=must_not_be_called)
    client._fixtures.mode = "live"
    search = SearchFinding()
    entity = make("312-555-8890", EntityType.PHONE)

    result = suggest_replacement(entity, finding_for(entity), client, search)

    assert result.suggested_replacement == "312-555-0190"
    assert result.replacement_verified is True
    assert search.probed == []


# --- Ce qui demande une invention, puis une re-vérification ---------------


def test_the_first_candidate_the_search_clears_is_kept():
    entity = make("The Black Cat Tavern", EntityType.BUSINESS)
    search = SearchFinding(real_names=("The Rusty Anchor",))

    result = suggest_replacement(
        entity,
        finding_for(entity),
        client_proposing("The Rusty Anchor", "The Paper Lantern"),
        search,
    )

    assert result.suggested_replacement == "The Paper Lantern"
    assert result.replacement_verified is True
    # Le premier candidat a bien été éliminé par la recherche, pas ignoré.
    assert len(search.probed) == 2


def test_a_candidate_the_search_finds_is_never_marked_verified():
    """Sans cette passe, on échangerait un piège contre un autre."""
    entity = make("The Black Cat Tavern", EntityType.BUSINESS)
    search = SearchFinding(real_names=("The Rusty Anchor", "The Paper Lantern"))

    result = suggest_replacement(
        entity,
        finding_for(entity),
        client_proposing("The Rusty Anchor", "The Paper Lantern"),
        search,
    )

    assert result.suggested_replacement == "The Rusty Anchor"
    assert result.replacement_verified is False


def test_the_replacement_is_probed_as_seriously_as_the_original():
    """Un remplacement validé par une requête plus faible ne vaudrait rien."""
    entity = make("Marcus Webb", EntityType.CHARACTER_NAME)
    search = SearchFinding()

    suggest_replacement(entity, finding_for(entity), client_proposing("Alan Ferris"), search)

    assert any("Alan Ferris" in q for q in search.probed)


def test_an_unverifiable_candidate_is_not_declared_verified():
    entity = make("The Black Cat Tavern", EntityType.BUSINESS)
    result = suggest_replacement(
        entity, finding_for(entity), client_proposing("The Paper Lantern"), SearchFinding(fail=True)
    )

    assert result.suggested_replacement == "The Paper Lantern"
    assert result.replacement_verified is False


def test_a_model_failure_leaves_the_finding_untouched():
    entity = make("The Black Cat Tavern", EntityType.BUSINESS)
    client = GeminiClient(transport=lambda _: {"json": "pas du json"})
    client._fixtures.mode = "live"

    result = suggest_replacement(entity, finding_for(entity), client, SearchFinding())
    assert result.suggested_replacement is None


# --- Ce qui ne se renomme pas --------------------------------------------


@pytest.mark.parametrize(
    "etype", [EntityType.SONG, EntityType.ARTWORK, EntityType.PUBLICATION, EntityType.REAL_PERSON]
)
def test_no_suggestion_where_renaming_would_be_bad_advice(etype):
    """On ne « renomme » pas une chanson sous droits : la sortie est une licence
    ou une coupe."""
    entity = make("Sweet Child O' Mine", etype)
    result = suggest_replacement(
        entity,
        finding_for(entity, Verdict.LICENSE_REQUIRED),
        client_proposing("Autre chose"),
        SearchFinding(),
    )
    assert result.suggested_replacement is None


def test_clear_verdicts_get_no_suggestion():
    entity = make("Coca-Cola", EntityType.PRODUCT_BRAND, ContextTier.NEUTRAL)
    result = suggest_replacement(
        entity, finding_for(entity, Verdict.CLEAR), client_proposing("Fizzy"), SearchFinding()
    )
    assert result.suggested_replacement is None


def test_batch_leaves_findings_without_a_matching_entity_alone():
    orphan = Finding(
        id="d1:ghost",
        entity_id="business:ghost",
        draft_id="d1",
        verdict=Verdict.CHANGE_RECOMMENDED,
        confidence=0.5,
        rationale="…",
    )
    out = suggest_replacements([orphan], [], client_proposing("X"), SearchFinding())
    assert out == [orphan]

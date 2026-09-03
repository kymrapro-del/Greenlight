"""Cache global de recherche.

L'architecture annonce le cache comme « le levier économique principal ». Ces
tests fixent ce qu'il garantit vraiment : que deux scénarios différents partagent
leurs entités, qu'ils ne partagent jamais deux entités homonymes de types
distincts, et qu'un échec n'est pas mémorisé.
"""

from __future__ import annotations

from greenlight.agents.research import research, research_entity
from greenlight.models import ContextTier, Entity, EntityType, Occurrence
from greenlight.tools.entity_cache import EntityCache, InMemoryCache
from greenlight.tools.parallel_search import ParallelSearch, SearchResponse, SearchResult


def make(name: str, etype: EntityType = EntityType.BUSINESS) -> Entity:
    return Entity(
        id=f"{etype.value.lower()}:{name.lower().replace(' ', '-')}",
        canonical_name=name,
        type=etype,
        occurrences=[Occurrence(scene_id="s1", scene_number=1, context_tier=ContextTier.NEUTRAL)],
    )


class CountingSearch(ParallelSearch):
    def __init__(self, fail: bool = False) -> None:
        super().__init__()
        self.calls = 0
        self.fail = fail

    def search(self, objective, search_queries, mode=None):  # type: ignore[override]
        self.calls += 1
        if self.fail:
            raise RuntimeError("amont indisponible")
        return SearchResponse(
            search_id="s", results=[SearchResult(url="https://a.test")], mode=mode or "fast"
        )


def test_the_same_entity_is_searched_once_across_two_scripts():
    """Le cas qui porte l'économie : Coca-Cola revient dans tous les scénarios."""
    cache, search = EntityCache(), CountingSearch()

    research_entity(make("Coca-Cola", EntityType.PRODUCT_BRAND), search, cache)
    second = research_entity(make("Coca-Cola", EntityType.PRODUCT_BRAND), search, cache)

    assert search.calls == 1
    assert second.cached is True
    assert second.response is not None


def test_a_spelling_variant_hits_the_same_entry():
    """La phase 3 canonicalise avant : le cache traverse les écritures."""
    cache, search = EntityCache(), CountingSearch()
    entity = make("The Black Cat Tavern")

    research_entity(entity, search, cache)
    research_entity(
        entity.model_copy(update={"canonical_name": "the black cat tavern"}), search, cache
    )

    assert search.calls == 1


def test_homonyms_of_different_types_never_share_results():
    """Une entreprise « Mercy » et un personnage « Mercy » ne sont pas la même
    chose : partager leurs résultats serait faux, pas économe."""
    cache, search = EntityCache(), CountingSearch()

    research_entity(make("Mercy", EntityType.BUSINESS), search, cache)
    research_entity(make("Mercy", EntityType.CHARACTER_NAME), search, cache)

    assert search.calls == 2


def test_a_failed_search_is_not_memorised():
    """Sinon une panne passagère serait figée pour trente jours."""
    cache, search = EntityCache(), CountingSearch(fail=True)

    research_entity(make("The Black Cat Tavern"), search, cache)
    research_entity(make("The Black Cat Tavern"), search, cache)

    assert search.calls == 2
    assert cache.stats()["hits"] == 0


def test_expired_entries_are_not_served():
    cache = EntityCache(InMemoryCache(ttl_s=-1))
    search = CountingSearch()

    research_entity(make("The Black Cat Tavern"), search, cache)
    research_entity(make("The Black Cat Tavern"), search, cache)

    assert search.calls == 2


def test_rule_resolved_entities_never_touch_the_cache():
    """Elles sont déjà gratuites : les compter en miss fausserait le taux."""
    cache, search = EntityCache(), CountingSearch()

    research_entity(make("555-0147", EntityType.PHONE), search, cache)

    assert cache.stats() == {"hits": 0, "misses": 0, "hit_rate": 0.0}


def test_the_run_reports_a_measured_hit_rate():
    cache, search = EntityCache(), CountingSearch()
    entities = [make("Acme Corp"), make("Acme Corp"), make("Other Corp")]

    run = research(entities, search, max_workers=1, cache=cache)

    assert search.calls == 2
    assert run.cache["hits"] == 1
    assert run.cache["hit_rate"] == round(1 / 3, 3)
    assert len(run.billed) == 2
    assert len(run.served_from_cache) == 1

"""Phase 4 — fan-out de recherche.

Le transport Parallel est simulé. Ce qui est testé ici, c'est la discipline
budgétaire du fan-out : ne pas chercher ce qui se tranche par règle, chercher au
bon prix, et ne jamais laisser un échec de recherche emporter le rapport.
"""

from __future__ import annotations

import threading

import pytest

from greenlight.agents.research import research, research_entity, scene_hint
from greenlight.models import ContextTier, Entity, EntityType, Occurrence
from greenlight.tools.parallel_search import ParallelSearch, SearchResponse, SearchResult


class FakeSearch(ParallelSearch):
    """Compte les appels réels et rend une réponse fabriquée."""

    def __init__(self, results: list[SearchResult] | None = None, fail: bool = False) -> None:
        super().__init__()
        self._results = results if results is not None else [SearchResult(url="https://a.test")]
        self._fail = fail
        self.calls: list[tuple[str, str]] = []
        self._calls_lock = threading.Lock()

    def search(self, objective, search_queries, mode=None):  # type: ignore[override]
        with self._calls_lock:
            self.calls.append((objective, mode or self.default_mode))
        if self._fail:
            raise RuntimeError("502 depuis l'amont")
        return SearchResponse(
            search_id="fake", results=list(self._results), mode=mode or self.default_mode
        )


def make(
    name: str,
    etype: EntityType = EntityType.BUSINESS,
    tier: ContextTier = ContextTier.NEUTRAL,
    quote: str = "",
) -> Entity:
    return Entity(
        id=f"{etype.value.lower()}:{name.lower()}",
        canonical_name=name,
        type=etype,
        occurrences=[Occurrence(scene_id="s1", scene_number=1, context_tier=tier, quote=quote)],
    )


# --- Discipline budgétaire ------------------------------------------------


def test_rule_resolved_entities_never_reach_the_api():
    search = FakeSearch()
    result = research_entity(make("555-0147", EntityType.PHONE), search)

    assert search.calls == [], "une entité tranchée par règle ne doit rien coûter"
    assert result.rule is not None
    assert not result.searched


def test_researched_entity_carries_its_sources():
    search = FakeSearch([SearchResult(url="https://en.wikipedia.org/wiki/Black_Cat")])
    result = research_entity(make("The Black Cat Tavern"), search)

    assert result.searched
    assert result.sources == ["https://en.wikipedia.org/wiki/Black_Cat"]


def test_depiction_decides_the_price_of_the_search():
    search = FakeSearch()
    research_entity(make("Acme Corp"), search)
    research_entity(make("The Black Cat Tavern", tier=ContextTier.ILLEGAL), search)

    assert [mode for _, mode in search.calls] == ["fast", "advanced"]


def test_only_billable_entities_are_searched_in_a_batch():
    search = FakeSearch()
    entities = [
        make("555-0147", EntityType.PHONE),
        make("dreyes@example.com", EntityType.URL_EMAIL),
        make("The Black Cat Tavern"),
        make("Mercy General Hospital", EntityType.INSTITUTION),
    ]
    run = research(entities, search, max_workers=4)

    assert len(search.calls) == 2
    assert len(run.skipped_by_rule) == 2
    assert len(run.results) == 4


# --- Robustesse -----------------------------------------------------------


def test_a_failed_search_is_recorded_not_swallowed():
    result = research_entity(make("The Black Cat Tavern"), FakeSearch(fail=True))

    assert result.error is not None and "502" in result.error
    assert not result.searched


def test_one_failure_does_not_take_down_the_batch():
    class FlakySearch(FakeSearch):
        def search(self, objective, search_queries, mode=None):  # type: ignore[override]
            if "Mercy" in objective:
                raise RuntimeError("timeout")
            return super().search(objective, search_queries, mode)

    run = research(
        [make("The Black Cat Tavern"), make("Mercy General Hospital", EntityType.INSTITUTION)],
        FlakySearch(),
        max_workers=2,
    )

    assert len(run.failed) == 1
    assert len(run.results) == 2


def test_input_order_is_preserved_under_concurrency():
    entities = [make(f"Business {i}") for i in range(20)]
    run = research(entities, FakeSearch(), max_workers=8)

    assert [r.entity.canonical_name for r in run.results] == [e.canonical_name for e in entities]


# --- Désambiguïsation -----------------------------------------------------


def test_hint_comes_from_the_most_serious_occurrence():
    """C'est la scène qui met l'entité en cause qui décrit le bon homonyme."""
    entity = Entity(
        id="character_name:marcus-webb",
        canonical_name="Marcus Webb",
        type=EntityType.CHARACTER_NAME,
        occurrences=[
            Occurrence(scene_id="s1", scene_number=1, quote="Webb walks in."),
            Occurrence(
                scene_id="s2",
                scene_number=2,
                context_tier=ContextTier.ILLEGAL,
                quote="Dr. Webb signs the forged prescription.",
            ),
        ],
    )
    assert "forged prescription" in scene_hint(entity)


def test_hint_survives_an_entity_without_quotes():
    assert scene_hint(make("Acme Corp")) == ""


@pytest.mark.parametrize("workers", [1, 4])
def test_serial_and_parallel_agree(workers):
    entities = [make("The Black Cat Tavern"), make("555-0147", EntityType.PHONE)]
    run = research(entities, FakeSearch(), max_workers=workers)

    assert [r.searched for r in run.results] == [True, False]

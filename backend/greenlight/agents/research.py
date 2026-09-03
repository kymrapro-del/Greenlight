"""Phase 4 — fan-out de recherche sur Parallel.

Le passage à l'échelle se joue ici. Un long métrage produit ~180 entités
canoniques ; les vérifier en série à ~3 s l'appel `advanced` mettrait dix
minutes et ferait tomber la démo. Trois leviers, dans cet ordre :

1. **Ne pas chercher.** Les entités tranchées par règle déterministe
   (`tools.queries.pre_verdict`) ne partent jamais dans la file. Sur le
   scénario de démonstration c'est un tiers des entités, et zéro requête
   facturée.
2. **Chercher au bon prix.** `fast` pour l'existence en contexte neutre,
   `advanced` là où le verdict est réellement en jeu. Cinq fois moins cher sur
   le volume, sans perdre en qualité là où ça compte.
3. **Chercher en parallèle.** Les entités sont indépendantes : rien ne justifie
   de les traiter en série.

Une recherche qui échoue n'emporte pas le rapport. L'entité redescend en
`UNRESOLVED` à la phase 5 — un trou signalé vaut infiniment mieux qu'un verdict
inventé.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from greenlight.models import Entity
from greenlight.tools.parallel_search import ParallelSearch, SearchResponse
from greenlight.tools.queries import PreVerdict, SearchSpec, build_search, pre_verdict


@dataclass
class ResearchResult:
    entity: Entity
    spec: SearchSpec | None = None
    response: SearchResponse | None = None
    # Renseigné quand une règle a tranché sans recherche.
    rule: PreVerdict | None = None
    error: str | None = None

    @property
    def searched(self) -> bool:
        return self.response is not None

    @property
    def sources(self) -> list[str]:
        return [r.url for r in self.response.results] if self.response else []


@dataclass
class ResearchRun:
    results: list[ResearchResult] = field(default_factory=list)
    usage: dict[str, float | int] = field(default_factory=dict)

    @property
    def by_entity(self) -> dict[str, ResearchResult]:
        return {r.entity.id: r for r in self.results}

    @property
    def skipped_by_rule(self) -> list[ResearchResult]:
        return [r for r in self.results if r.rule is not None]

    @property
    def failed(self) -> list[ResearchResult]:
        return [r for r in self.results if r.error]


def scene_hint(entity: Entity) -> str:
    """Le meilleur extrait disponible pour désambiguïser la recherche.

    On prend la citation de l'occurrence la plus grave : c'est celle qui décrit
    l'entité telle qu'elle est mise en cause, donc celle qui a le plus de chance
    de faire remonter le bon homonyme.
    """
    if not entity.occurrences:
        return ""
    worst = entity.worst_context
    for occurrence in entity.occurrences:
        if occurrence.context_tier is worst and occurrence.quote:
            return occurrence.quote[:160]
    return entity.occurrences[0].quote[:160]


def research_entity(entity: Entity, search: ParallelSearch) -> ResearchResult:
    rule = pre_verdict(entity)
    if rule is not None:
        # Tranché sans réseau : ni latence, ni crédit.
        return ResearchResult(entity=entity, rule=rule)

    spec = build_search(entity, scene_hint=scene_hint(entity))
    try:
        response = search.search(spec.objective, spec.queries, mode=spec.mode)
    except Exception as exc:
        return ResearchResult(entity=entity, spec=spec, error=f"{type(exc).__name__}: {exc}")
    return ResearchResult(entity=entity, spec=spec, response=response)


def research(
    entities: list[Entity],
    search: ParallelSearch | None = None,
    max_workers: int = 8,
) -> ResearchRun:
    """Lance le fan-out. L'ordre d'entrée est conservé en sortie."""
    search = search or ParallelSearch()

    if max_workers <= 1 or len(entities) <= 1:
        results = [research_entity(e, search) for e in entities]
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            results = list(pool.map(lambda e: research_entity(e, search), entities))

    return ResearchRun(results=results, usage=search.usage_summary())

"""Phase 8 — diff entre deux versions d'un scénario.

Un scénario est réécrit dix à trente fois. Refaire une passe complète à chaque
version coûterait autant que la première et prendrait autant de temps : le
scénariste ne relancerait l'outil qu'une fois, à la fin — c'est-à-dire trop
tard, exactement le problème qu'on essaie de régler. Le diff est donc ce qui
rend l'outil utilisable pendant l'écriture plutôt qu'après.

**Ce qui est réutilisé, et sous quelles conditions.** Un verdict de la version
précédente est repris tel quel seulement si rien de ce qui l'a produit n'a
bougé :

1. l'entité est la même — l'identifiant est dérivé du type et du nom
   canonicalisé, donc une simple variante d'écriture ne casse pas la
   réutilisation ;
2. la dépiction la plus grave est inchangée — c'est elle qui pilote à la fois la
   profondeur de recherche et la règle d'escalade, donc une entité qui passe de
   neutre à délictueuse doit être réanalysée même si son nom n'a pas changé ;
3. le verdict a été produit par la version de prompt courante — sinon il est
   périmé, et le réutiliser ferait mentir le rapport après chaque évolution du
   prompt.

Tout le reste — entité nouvelle, dépiction déplacée, verdict périmé — repart
dans le pipeline. C'est un cache dont les conditions d'invalidation sont
explicites, pas une optimisation opportuniste.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from greenlight.agents.classify import PROMPT_VERSION
from greenlight.models import Entity, Finding


@dataclass
class DraftDiff:
    """Ce qui a changé entre deux versions, et ce que ça implique de recalculer."""

    added: list[Entity] = field(default_factory=list)
    removed: list[Entity] = field(default_factory=list)
    # Entité conservée, mais dépeinte différemment : le verdict peut basculer.
    recontextualized: list[Entity] = field(default_factory=list)
    # Entité conservée à l'identique, mais dont le verdict est périmé.
    stale: list[Entity] = field(default_factory=list)
    reused: list[Finding] = field(default_factory=list)

    @property
    def to_analyze(self) -> list[Entity]:
        """Les seules entités qui repartent dans le pipeline."""
        return self.added + self.recontextualized + self.stale

    @property
    def unchanged_count(self) -> int:
        return len(self.reused)

    def summary(self) -> str:
        total = len(self.to_analyze) + self.unchanged_count
        if total == 0:
            return "Aucune entité dans cette version."
        saved = self.unchanged_count
        return (
            f"{len(self.to_analyze)} entités à réanalyser sur {total} — "
            f"{saved} verdicts repris de la version précédente "
            f"({saved * 100 // total} % de la recherche évitée)"
        )


def plan(
    previous_entities: list[Entity],
    previous_findings: list[Finding],
    current_entities: list[Entity],
    draft_id: str,
    prompt_version: str = PROMPT_VERSION,
) -> DraftDiff:
    """Décide, entité par entité, ce qui se réutilise et ce qui se recalcule."""
    before = {e.id: e for e in previous_entities}
    findings = {f.entity_id: f for f in previous_findings}
    current_ids = {e.id for e in current_entities}

    diff = DraftDiff(removed=[e for e in previous_entities if e.id not in current_ids])

    for entity in current_entities:
        previous = before.get(entity.id)
        if previous is None:
            diff.added.append(entity)
            continue

        if previous.worst_context is not entity.worst_context:
            diff.recontextualized.append(entity)
            continue

        finding = findings.get(entity.id)
        if finding is None or finding.prompt_version != prompt_version:
            diff.stale.append(entity)
            continue

        # Rien de ce qui a produit ce verdict n'a bougé : on le reporte sur la
        # nouvelle version, sans le recalculer.
        diff.reused.append(
            finding.model_copy(update={"draft_id": draft_id, "id": f"{draft_id}:{entity.id}"})
        )

    return diff

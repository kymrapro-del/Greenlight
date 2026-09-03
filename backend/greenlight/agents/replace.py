"""Phase 6 — remplacements re-vérifiés.

Signaler un problème sans proposer de sortie renvoie le travail au scénariste.
Cette phase propose un nom de remplacement, **puis le repasse par la même
recherche que l'entité d'origine**. Un remplacement n'est déclaré vérifié que
si la recherche ne trouve rien de réel derrière. Sans cette seconde passe, on
se contenterait d'échanger un piège contre un autre — un modèle qui invente un
nom de bar « qui sonne fictif » a une chance non négligeable de tomber sur un
établissement qui existe.

Deux régimes, et le premier est le plus important :

**Ce que la convention professionnelle tranche déjà.** Un numéro de téléphone
se remplace par un 555-01XX, une adresse e-mail par un domaine réservé RFC 2606.
Ces réponses sont connues, gratuites, et sûres par construction. Aucun appel
modèle, aucune recherche, aucune vérification nécessaire : la plage est
réservée à la fiction, c'est tout.

**Ce qui demande de l'invention.** Un nom de bar, d'hôpital, de personnage.
Là, le modèle propose plusieurs candidats et on retient le premier que la
recherche ne rattache à rien.

Ce qui n'est pas remplaçable ne reçoit pas de suggestion. On ne « renomme » pas
une chanson sous droits ni un tableau de Hopper : la sortie est une licence ou
une coupe, et prétendre le contraire serait un mauvais conseil.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from greenlight.agents.gemini import GeminiClient
from greenlight.config import settings
from greenlight.models import Entity, EntityType, Finding, Verdict
from greenlight.tools.parallel_search import ParallelSearch
from greenlight.tools.queries import build_search

# Catégories où renommer règle réellement le problème.
RENAMEABLE = {
    EntityType.CHARACTER_NAME,
    EntityType.BUSINESS,
    EntityType.INSTITUTION,
    EntityType.ADDRESS,
    EntityType.PHONE,
    EntityType.URL_EMAIL,
    EntityType.LICENSE_PLATE,
    EntityType.PRODUCT_BRAND,
    EntityType.SPORTS_TEAM,
    EntityType.VEHICLE,
}

# Verdicts qui appellent une suggestion. `CAUTION` en reçoit une aussi : elle ne
# coûte presque rien et évite au scénariste d'avoir à y revenir.
NEEDS_REPLACEMENT = {Verdict.CHANGE_RECOMMENDED, Verdict.CAUTION}


class ReplacementCandidates(BaseModel):
    """responseSchema de la phase 6."""

    candidates: list[str] = Field(default_factory=list)


SYSTEM_INSTRUCTION = """\
You are helping a screenwriter rename an entity that failed clearance.

Propose 3 replacement names. They must:
- fit the same category, register and period as the original, so the scene reads
  identically after the swap;
- keep the same rhythm and length where possible — a name the writer would have
  chosen anyway;
- be plausible in the story's setting;
- be unlikely to belong to a real, identifiable person, business or institution.

Do not explain. Return the names only, most promising first.

Avoid: real places you know of, celebrity names, obvious jokes, and anything so \
generic it will match hundreds of real businesses.
"""


# --------------------------------------------------------------------------
# 1. Ce que la convention tranche — gratuit, instantané, sûr par construction
# --------------------------------------------------------------------------

_LOCAL_PART = re.compile(r"^[^@]+")


def conventional_replacement(entity: Entity) -> str | None:
    """Réponse dictée par la convention professionnelle, ou None."""
    if entity.type is EntityType.PHONE:
        # Le NANP réserve 555-0100 à 555-0199 à la fiction. On garde l'indicatif
        # d'origine s'il y en a un : la réplique sonne pareil.
        digits = re.sub(r"\D", "", entity.canonical_name)
        area = digits[:3] if len(digits) >= 10 else ""
        suffix = f"555-01{int(digits[-2:] or 0) % 100:02d}"
        return f"{area}-{suffix}" if area else suffix

    if entity.type is EntityType.URL_EMAIL and "@" in entity.canonical_name:
        local = _LOCAL_PART.match(entity.canonical_name)
        return f"{local.group(0) if local else 'contact'}@example.com"

    return None


# --------------------------------------------------------------------------
# 2. Ce qui demande une invention — et une re-vérification
# --------------------------------------------------------------------------


def build_prompt(entity: Entity, finding: Finding) -> str:
    quotes = [o.quote for o in entity.occurrences if o.quote][:2]
    return "\n".join(
        [
            f"NAME TO REPLACE: {entity.canonical_name}",
            f"CATEGORY: {entity.type.value}",
            f"WHY IT FAILED: {finding.rationale}",
            "",
            "HOW IT IS USED IN THE SCRIPT:",
            *(f"  - {q}" for q in quotes),
        ]
    )


def _probe_entity(entity: Entity, candidate: str) -> Entity:
    """L'entité telle qu'elle serait après remplacement, pour la re-vérifier."""
    return entity.model_copy(update={"canonical_name": candidate, "aliases": []})


def verify_candidate(entity: Entity, candidate: str, search: ParallelSearch) -> bool:
    """Vrai si la recherche ne rattache le candidat à rien de réel.

    On réutilise exactement la stratégie de recherche de l'entité d'origine : un
    remplacement vérifié par une requête plus faible ne vaudrait rien.
    """
    spec = build_search(_probe_entity(entity, candidate))
    try:
        response = search.search(spec.objective, spec.queries, mode=spec.mode)
    except Exception:
        # Impossible de vérifier : on ne déclare pas vérifié pour autant.
        return False
    return response.is_empty


def suggest_replacement(
    entity: Entity,
    finding: Finding,
    client: GeminiClient,
    search: ParallelSearch,
    max_candidates: int = 3,
    model: str | None = None,
) -> Finding:
    """Renseigne `suggested_replacement` et `replacement_verified` sur le finding."""
    if finding.verdict not in NEEDS_REPLACEMENT or entity.type not in RENAMEABLE:
        return finding

    conventional = conventional_replacement(entity)
    if conventional is not None:
        # Plage réservée à la fiction : sûre par construction, rien à vérifier.
        return finding.model_copy(
            update={"suggested_replacement": conventional, "replacement_verified": True}
        )

    try:
        proposal = client.structured(
            model=model or settings.model_extract,
            system=SYSTEM_INSTRUCTION,
            prompt=build_prompt(entity, finding),
            schema=ReplacementCandidates,
            # Un peu de latitude : trois variantes identiques n'aideraient pas.
            temperature=0.7,
        )
    except Exception:
        return finding

    candidates = [c.strip() for c in proposal.candidates if c.strip()][:max_candidates]
    fallback: str | None = candidates[0] if candidates else None

    for candidate in candidates:
        if verify_candidate(entity, candidate, search):
            return finding.model_copy(
                update={"suggested_replacement": candidate, "replacement_verified": True}
            )

    # Aucun candidat n'est sorti indemne de la re-vérification. On propose quand
    # même le premier, en le marquant non vérifié : le scénariste voit la
    # différence, et c'est cette honnêteté qui rend la suggestion utilisable.
    return finding.model_copy(
        update={"suggested_replacement": fallback, "replacement_verified": False}
    )


def suggest_replacements(
    findings: list[Finding],
    entities: list[Entity],
    client: GeminiClient | None = None,
    search: ParallelSearch | None = None,
    model: str | None = None,
) -> list[Finding]:
    client = client or GeminiClient()
    search = search or ParallelSearch()
    by_id = {e.id: e for e in entities}

    out = []
    for finding in findings:
        entity = by_id.get(finding.entity_id)
        if entity is None:
            out.append(finding)
            continue
        out.append(suggest_replacement(entity, finding, client, search, model=model))
    return out

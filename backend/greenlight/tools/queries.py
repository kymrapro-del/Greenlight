"""Stratégie de recherche par type d'entité — le cœur métier de la phase 4.

Deux idées, et ce sont elles qui séparent GREENLIGHT d'un simple
« LLM + recherche web » :

1. PRÉ-VERDICTS DÉTERMINISTES
   Certaines entités se tranchent sans aucun appel réseau, par convention
   professionnelle. Un numéro en 555-01XX est réservé à la fiction depuis
   toujours : il est `CLEAR`, point. Aucune raison de payer une recherche.
   Ces règles s'exécutent avant le fan-out et retirent typiquement 10 à 15 %
   des entités de la file.

2. ROUTAGE PAR NIVEAU DE RISQUE
   `fast` (1 $/1000) suffit pour vérifier l'existence d'une entité citée en
   contexte neutre. `advanced` (5 $/1000) n'est justifié que là où le verdict
   est réellement en jeu : entité dépeinte défavorablement, ou catégorie à
   forte exposition juridique. Cinq fois moins cher sur le volume, sans perdre
   en qualité là où ça compte.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from greenlight.models import ContextTier, Entity, EntityType, Verdict
from greenlight.tools.parallel_search import Mode

# --------------------------------------------------------------------------
# 1. Pré-verdicts déterministes — aucun appel réseau
# --------------------------------------------------------------------------

# Le NANP réserve 555-0100 à 555-0199 à la fiction. Convention respectée par
# toute l'industrie ; un numéro dans cette plage ne pose aucun problème.
_FICTIONAL_PHONE = re.compile(r"555[\s\-\.]?01\d{2}")
_SAFE_DOMAINS = ("example.com", "example.org", "example.net", "test.com")


@dataclass
class PreVerdict:
    verdict: Verdict
    rationale: str


def pre_verdict(entity: Entity) -> PreVerdict | None:
    """Verdict tranché par règle, sans recherche. None = il faut chercher."""
    name = entity.canonical_name.strip()
    lowered = name.lower()

    if entity.type is EntityType.PHONE:
        if _FICTIONAL_PHONE.search(name):
            return PreVerdict(
                Verdict.CLEAR,
                "Numéro dans la plage 555-0100/555-0199, réservée à la fiction "
                "par le plan de numérotation nord-américain. Aucun risque.",
            )
        return PreVerdict(
            Verdict.CHANGE_RECOMMENDED,
            "Numéro hors de la plage fictive 555-01XX : il peut correspondre à "
            "une ligne réellement attribuée. Remplacer par un 555-01XX.",
        )

    if entity.type is EntityType.URL_EMAIL and any(d in lowered for d in _SAFE_DOMAINS):
        return PreVerdict(
            Verdict.CLEAR,
            "Domaine réservé à la documentation par la RFC 2606. Aucun risque.",
        )

    if entity.type is EntityType.GOVERNMENT_AGENCY and entity.worst_context is ContextTier.NEUTRAL:
        return PreVerdict(
            Verdict.CLEAR,
            "Organisme public cité de façon neutre : l'usage nominatif d'une "
            "administration ne demande pas d'autorisation.",
        )

    return None


# --------------------------------------------------------------------------
# 2. Construction des requêtes
# --------------------------------------------------------------------------

# Catégories où le verdict engage un vrai risque juridique, quel que soit
# le contexte : on y met le mode le plus profond.
_HIGH_STAKES = {
    EntityType.SONG,
    EntityType.ARTWORK,
    EntityType.REAL_PERSON,
    EntityType.REAL_EVENT,
    EntityType.PUBLICATION,
}


@dataclass
class SearchSpec:
    objective: str
    queries: list[str]
    mode: Mode


def choose_mode(entity: Entity) -> Mode:
    if entity.type in _HIGH_STAKES:
        return "advanced"
    if entity.worst_context is not ContextTier.NEUTRAL:
        # L'entité est montrée sous un jour défavorable ou illégal : le verdict
        # se joue ici, on paie la recherche profonde.
        return "advanced"
    return "fast"


def build_search(entity: Entity, scene_hint: str = "") -> SearchSpec:
    """Produit l'objectif et les requêtes adaptés au type d'entité."""
    name = entity.canonical_name
    q = f'"{name}"'
    hint = f" {scene_hint}" if scene_hint else ""

    match entity.type:
        case EntityType.CHARACTER_NAME:
            objective = (
                f"Determine whether a real, identifiable living person named {name} exists, "
                f"especially anyone matching this description: {scene_hint or 'unspecified'}. "
                "Report notable individuals, professionals, and public figures with this exact name."
            )
            queries = [f"{q}{hint}", f"{q} person profile", f"{q} news"]

        case EntityType.BUSINESS:
            objective = (
                f"Determine whether a real business or company named {name} exists, "
                "who owns it, where it operates, and whether the name is a registered trademark."
            )
            queries = [f"{q} company", f"{q} trademark registration", f"{q} business{hint}"]

        case EntityType.PRODUCT_BRAND:
            objective = (
                f"Identify the trademark owner of the brand {name}, the goods it covers, "
                "and whether the mark is currently active."
            )
            queries = [f"{q} brand owner", f"{q} trademark class", f"{q} official site"]

        case EntityType.SONG:
            objective = (
                f'Identify the songwriters, publisher and current rights holders of the song "{name}", '
                "its year of release, and whether it is in the public domain."
            )
            queries = [
                f"{q} song publisher rights",
                f"{q} songwriter copyright",
                f"{q} public domain",
            ]

        case EntityType.ARTWORK:
            objective = (
                f"Identify the creator, creation date, current rights holder and copyright status "
                f'of the artwork "{name}".'
            )
            queries = [
                f"{q} artist copyright",
                f"{q} public domain status",
                f"{q} museum collection",
            ]

        case EntityType.INSTITUTION:
            objective = (
                f"Determine whether a real institution named {name} exists "
                f"({scene_hint or 'type unspecified'}), where it is located, and who operates it."
            )
            queries = [f"{q} institution{hint}", f"{q} official", f"{q} location"]

        case EntityType.REAL_PERSON:
            objective = (
                f"Identify who {name} is, whether they are living, and any publicity-rights or "
                "defamation exposure from depicting them in a dramatic work."
            )
            queries = [f"{q} biography", f"{q} living or deceased", f"{q} publicity rights"]

        case EntityType.REAL_EVENT:
            objective = (
                f"Establish the factual record of the event known as {name}: what happened, when, "
                "who was involved, and which accounts are disputed."
            )
            queries = [f"{q} what happened", f"{q} timeline", f"{q} disputed account"]

        case EntityType.ADDRESS:
            objective = (
                f"Determine whether the address {name} corresponds to a real, occupied property, "
                "and what is located there."
            )
            queries = [f"{q} address", f"{q} property"]

        case EntityType.PUBLICATION:
            objective = (
                f'Identify the publisher and rights holder of "{name}" and whether it is a real '
                "publication still in copyright."
            )
            queries = [f"{q} publisher", f"{q} copyright status"]

        case EntityType.SPORTS_TEAM:
            objective = (
                f"Determine whether {name} is a real sports team, who owns the name and logo, "
                "and what licensing its depiction requires."
            )
            queries = [f"{q} team", f"{q} trademark licensing"]

        case EntityType.VEHICLE | EntityType.LICENSE_PLATE:
            objective = (
                f"Determine whether {name} corresponds to a real, registered vehicle identifier "
                "or a protected vehicle design."
            )
            queries = [f"{q} registration", f"{q} vehicle"]

        case _:
            objective = (
                f"Determine whether {name} refers to a real, identifiable entity in the world."
            )
            queries = [q, f"{q}{hint}"]

    return SearchSpec(objective=objective, queries=queries[:3], mode=choose_mode(entity))

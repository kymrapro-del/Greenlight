"""Phase 3 — canonicalisation des entités à l'échelle du scénario.

Entièrement déterministe : aucun appel modèle, aucun coût, un test qui tranche.

Ce que ça règle. Un scénario nomme la même entité de dix façons : `THE BLACK
CAT TAVERN` dans une en-tête, « the Black Cat » dans l'action, `WEBB` au-dessus
d'un dialogue et « Dr. Marcus Webb » dans une réplique. Sans cette phase, le
fan-out paie quatre recherches Parallel pour une seule entité et le rapport
affiche quatre lignes là où le scénariste en attend une.

Deux règles de fusion, volontairement conservatrices — un faux positif de fusion
masquerait un vrai risque, c'est la pire erreur possible ici :

1. Même type et même forme normalisée (casse, ponctuation, article de tête et
   titre honorifique retirés).
2. Même type, et un nom d'un seul mot qui correspond au nom de famille d'un
   *unique* nom composé. `WEBB` rejoint « Marcus Webb ». S'il y avait aussi une
   « Sarah Webb », l'ambiguïté interdit la fusion et les deux restent séparées.

Le nom canonique retenu est la variante la plus complète : c'est elle qui porte
le plus d'information pour la recherche, et c'est celle que le scénariste
reconnaît.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable

from greenlight.agents.extract import SceneEntities
from greenlight.models import Entity, EntityType, Occurrence

# Titres et articles retirés avant comparaison : ils varient d'une occurrence à
# l'autre sans jamais désigner une entité différente.
_HONORIFICS = (
    "dr",
    "doctor",
    "mr",
    "mrs",
    "ms",
    "miss",
    "det",
    "detective",
    "officer",
    "sgt",
    "sergeant",
    "capt",
    "captain",
    "lt",
    "lieutenant",
    "prof",
    "professor",
    "nurse",
    "father",
    "sister",
)
_LEADING_ARTICLES = ("the", "a", "an", "le", "la", "les")

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """'Dr. Marcus Webb' -> 'marcus webb' ; 'THE Black Cat' -> 'black cat'."""
    text = _PUNCT.sub(" ", name.lower())
    tokens = [t for t in _SPACES.split(text) if t]
    while tokens and tokens[0] in _HONORIFICS:
        tokens.pop(0)
    while tokens and tokens[0] in _LEADING_ARTICLES:
        tokens.pop(0)
    return " ".join(tokens)


def entity_id(etype: EntityType, canonical: str) -> str:
    """Identifiant stable et lisible : deux runs sur le même draft donnent les
    mêmes identifiants, donc le diff de la phase 8 peut les comparer."""
    slug = _SPACES.sub("-", normalize_name(canonical)) or "unnamed"
    return f"{etype.value.lower()}:{slug}"


# La fusion par nom de famille ne vaut que pour les personnes : « Tavern » ne
# désigne pas « Black Cat Tavern ».
_PERSON_TYPES = (EntityType.CHARACTER_NAME, EntityType.REAL_PERSON)


def _surname_merge(
    keys: Iterable[tuple[EntityType, str]],
) -> dict[tuple[EntityType, str], str]:
    """Table de redirection 'webb' -> 'marcus webb', quand elle est sans ambiguïté."""
    redirect: dict[tuple[EntityType, str], str] = {}
    by_type: dict[EntityType, list[str]] = defaultdict(list)
    for etype, norm in keys:
        by_type[etype].append(norm)

    for etype in _PERSON_TYPES:
        names = by_type.get(etype, [])
        singles = [n for n in names if " " not in n]
        composites = [n for n in names if " " in n]
        for single in singles:
            matches = [c for c in composites if c.split()[-1] == single]
            # Un seul candidat, sinon l'ambiguïté interdit la fusion.
            if len(matches) == 1:
                redirect[(etype, single)] = matches[0]
    return redirect


def canonicalize(scene_entities: list[SceneEntities]) -> list[Entity]:
    """Agrège les extractions par scène en entités canoniques du scénario."""
    # (type, forme normalisée) -> occurrences accumulées + variantes vues
    groups: dict[tuple[EntityType, str], list[tuple[str, Occurrence]]] = defaultdict(list)

    for bundle in scene_entities:
        for extracted in bundle.entities:
            norm = normalize_name(extracted.name)
            if not norm:
                continue
            occurrence = Occurrence(
                scene_id=bundle.scene.id,
                scene_number=bundle.scene.number,
                context_tier=extracted.context_tier,
                quote=extracted.quote or extracted.name,
            )
            groups[(extracted.type, norm)].append((extracted.name, occurrence))

    redirect = _surname_merge(groups.keys())

    merged: dict[tuple[EntityType, str], list[tuple[str, Occurrence]]] = defaultdict(list)
    for key, items in groups.items():
        merged[(key[0], redirect.get(key, key[1]))].extend(items)

    entities: list[Entity] = []
    for (etype, _norm), items in merged.items():
        variants = [name for name, _ in items]
        # La variante la plus complète devient le nom canonique : c'est celle
        # qui porte le plus d'information pour la recherche. À longueur égale on
        # écarte les capitales, qui sont un artefact de format — en-tête de scène
        # ou cue de dialogue — et non l'écriture voulue par le scénariste ; puis
        # on préfère l'initiale majuscule, qui est l'écriture attendue d'un nom
        # propre dans le rapport.
        canonical = max(
            variants,
            key=lambda v: (len(normalize_name(v)), not v.isupper(), v[:1].isupper(), len(v)),
        )
        aliases = sorted({v for v in variants if v != canonical})
        entities.append(
            Entity(
                id=entity_id(etype, canonical),
                canonical_name=canonical,
                type=etype,
                aliases=aliases,
                occurrences=[occ for _, occ in items],
            )
        )

    # Ordre stable : les entités les plus présentes d'abord, puis alphabétique.
    entities.sort(key=lambda e: (-len(e.occurrences), e.canonical_name.lower()))
    return entities

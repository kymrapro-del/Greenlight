"""Phase 2 — extraction des entités, scène par scène.

Deux choix structurants ici.

**Une scène = un appel.** Découper plutôt qu'envoyer le scénario entier donne
trois choses : un contexte court donc une extraction précise, un parallélisme
naturel sur le fan-out, et un échec isolé — une scène qui casse ne fait pas
tomber le rapport.

**Le modèle rend deux signaux, pas un.** Il ne dit pas seulement « voici une
entreprise », il dit *comment la scène la dépeint* (`context_tier`). C'est ce
second signal qui porte tout le produit : la même enseigne réelle est
inoffensive dans un plan de coupe et devient un risque de diffamation dès qu'un
personnage y commet un délit. Un système qui n'extrait que l'existence peint
tout en rouge et ne sert à rien.

**Garde-fou anti-hallucination.** Une entité citée par le modèle mais absente
du texte de la scène est écartée avant toute recherche. C'est déterministe,
gratuit, et ça évite le pire scénario de démo : payer une recherche Parallel
pour un nom que le scénariste n'a jamais écrit.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from greenlight.agents.gemini import GeminiClient
from greenlight.config import settings
from greenlight.models import Draft, ExtractedEntity, Scene, SceneExtraction

SYSTEM_INSTRUCTION = """\
You are a script clearance analyst. Your job is the entity-extraction pass that \
precedes a legal clearance report on a screenplay.

For the single scene you are given, list every entity that a clearance report \
would have to check against the real world. Work only from the text provided.

For each entity, return:

1. `name` — copied VERBATIM from the scene text. Never normalise, expand, \
translate or correct it. If the scene says "the Black Cat", the name is \
"the Black Cat".
2. `type` — one of the allowed categories.
3. `quote` — the shortest span of the scene text that shows the entity in use.
4. `context_tier` — how THIS scene depicts the entity:
   - `neutral`: mentioned, present, or used incidentally. Nothing in the scene \
reflects badly on it.
   - `unflattering`: shown as dirty, unsafe, incompetent, failing, or morally \
compromised.
   - `illegal`: a crime, or conduct that could be defamatory, happens at it, to \
it, or through it.

The `context_tier` is the most important field you produce. Judge the depiction, \
not the entity. A famous soft-drink can sitting on a windowsill is `neutral`. A \
bar where a character sells narcotics is `illegal`, even if the bar is only \
named once in a scene heading.

Rules:
- Extract fictional-looking entities too. Deciding what is real is a later \
stage's job, not yours.
- A character who only speaks, with no other identifying detail, is still a \
CHARACTER_NAME.
- Do not invent entities. Do not list generic nouns ("the bar", "a hospital") \
with no proper name.
- Return an empty list rather than guessing when the scene names nothing.
"""


def build_prompt(scene: Scene) -> str:
    parts = [f"SCENE {scene.number}", scene.heading, ""]
    if scene.action:
        parts += ["ACTION:", scene.action, ""]
    if scene.dialogue:
        parts += ["DIALOGUE:", "\n".join(scene.dialogue)]
    return "\n".join(parts).strip()


# --------------------------------------------------------------------------
# Garde-fou anti-hallucination
# --------------------------------------------------------------------------

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _normalize(text: str) -> str:
    """Réduit à l'essentiel comparable : casse, ponctuation et espaces sautent.

    Cette normalisation fait tenir ensemble les écritures d'un même token :
    `312-555-8890` et `(312) 555 8890`, `Sweet Child O' Mine` et
    `Sweet Child O Mine`.
    """
    return _NON_ALNUM.sub("", text.lower())


def appears_in(name: str, scene_text: str) -> bool:
    normalized = _normalize(name)
    if not normalized:
        return False
    return normalized in _normalize(scene_text)


@dataclass
class SceneEntities:
    scene: Scene
    entities: list[ExtractedEntity] = field(default_factory=list)
    # Écartées par le garde-fou. Conservées pour l'observabilité : le taux
    # d'hallucination est une métrique, pas un détail à masquer.
    dropped: list[ExtractedEntity] = field(default_factory=list)
    # Renseigné quand la scène a échoué. Une scène perdue reste visible dans le
    # rapport plutôt que de disparaître en silence.
    error: str | None = None


def filter_hallucinations(
    entities: list[ExtractedEntity], scene: Scene
) -> tuple[list[ExtractedEntity], list[ExtractedEntity]]:
    haystack = f"{scene.heading}\n{scene.action}\n" + "\n".join(scene.dialogue)
    kept, dropped = [], []
    for entity in entities:
        (kept if appears_in(entity.name, haystack) else dropped).append(entity)
    return kept, dropped


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------


def extract_scene(scene: Scene, client: GeminiClient, model: str | None = None) -> SceneEntities:
    """Extrait les entités d'une scène. Une scène, un appel, un schéma."""
    result = client.structured(
        model=model or settings.model_extract,
        system=SYSTEM_INSTRUCTION,
        prompt=build_prompt(scene),
        schema=SceneExtraction,
    )
    kept, dropped = filter_hallucinations(result.entities, scene)
    return SceneEntities(scene=scene, entities=kept, dropped=dropped)


def extract_draft(
    draft: Draft,
    client: GeminiClient | None = None,
    model: str | None = None,
    max_workers: int = 8,
) -> list[SceneEntities]:
    """Extrait tout un draft. Une scène en échec n'emporte pas le rapport.

    Les scènes sont indépendantes, donc traitées en parallèle. Ce n'est pas une
    micro-optimisation : un long métrage fait une centaine de scènes, et les
    enchaîner en série mettrait plusieurs minutes avant même que la première
    recherche ne parte. C'est le vrai goulot de bout en bout, le fan-out en aval
    n'y change rien.
    """
    client = client or GeminiClient()

    def one(scene: Scene) -> SceneEntities:
        try:
            return extract_scene(scene, client, model=model)
        except Exception as exc:
            return SceneEntities(scene=scene, error=f"{type(exc).__name__}: {exc}")

    if max_workers <= 1 or len(draft.scenes) <= 1:
        return [one(scene) for scene in draft.scenes]

    # `map` préserve l'ordre d'entrée : les scènes restent dans l'ordre du script.
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(one, draft.scenes))

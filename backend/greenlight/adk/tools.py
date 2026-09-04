"""Les capacités de GREENLIGHT exposées en outils ADK.

Un outil ADK est une fonction typée, documentée, appelable par un agent. Les
docstrings ne sont donc pas décoratives : c'est à partir d'elles que l'ADK
construit la déclaration passée au modèle. Elles sont écrites en anglais pour
cette raison.

Ces outils enveloppent le code existant sans le dupliquer. La stratégie de
requêtes, le routage par niveau de risque et les pré-verdicts déterministes
restent définis dans `greenlight.tools.queries` — un seul endroit à corriger.
"""

from __future__ import annotations

from typing import Any

from google.adk.tools import FunctionTool

from greenlight.models import ContextTier, Entity, EntityType, Occurrence
from greenlight.tools.parallel_search import ParallelSearch
from greenlight.tools.queries import build_search, choose_mode, pre_verdict


def _entity_from(name: str, entity_type: str, context_tier: str) -> Entity:
    etype = EntityType(entity_type)
    tier = ContextTier(context_tier)
    return Entity(
        id=f"{etype.value.lower()}:{name.lower()}",
        canonical_name=name,
        type=etype,
        occurrences=[Occurrence(scene_id="ad-hoc", scene_number=0, context_tier=tier)],
    )


def check_clearance_rule(name: str, entity_type: str, context_tier: str) -> dict[str, Any]:
    """Settle an entity by professional convention, without any web search.

    Some clearance questions have known answers: a phone number in the
    555-0100-555-0199 range is reserved for fiction, an example.com address is
    reserved by RFC 2606, a government agency named neutrally needs no
    permission. Call this before searching — it is free and instant.

    Args:
        name: The entity as written in the screenplay, verbatim.
        entity_type: One of the clearance categories, e.g. PHONE, URL_EMAIL,
            BUSINESS, CHARACTER_NAME, GOVERNMENT_AGENCY.
        context_tier: How the scene depicts it: neutral, unflattering, illegal.

    Returns:
        A dict with `settled` (bool). When true, `verdict` and `rationale`
        give the answer and no search is needed. When false, the entity must
        be researched.
    """
    rule = pre_verdict(_entity_from(name, entity_type, context_tier))
    if rule is None:
        return {"settled": False}
    return {"settled": True, "verdict": rule.verdict.value, "rationale": rule.rationale}


def research_entity_on_the_web(
    name: str, entity_type: str, context_tier: str, scene_hint: str = ""
) -> dict[str, Any]:
    """Search the live web for a real-world counterpart to a screenplay entity.

    The search objective, the queries and the search depth are all chosen from
    the entity's category and from how the scene depicts it. Depth costs money,
    so it is spent only where the verdict is genuinely in play.

    Args:
        name: The entity as written in the screenplay, verbatim.
        entity_type: One of the clearance categories, e.g. BUSINESS, SONG,
            CHARACTER_NAME, INSTITUTION, ARTWORK.
        context_tier: How the scene depicts it: neutral, unflattering, illegal.
        scene_hint: A short quote showing the entity in use, which
            disambiguates between namesakes.

    Returns:
        A dict with `mode` (the search depth used), `results` (each with url,
        title and excerpts) and `cost_usd` for this call.
    """
    entity = _entity_from(name, entity_type, context_tier)
    spec = build_search(entity, scene_hint=scene_hint)
    search = ParallelSearch()
    response = search.search(spec.objective, spec.queries, mode=spec.mode)
    return {
        "mode": response.mode,
        "cost_usd": response.cost_usd,
        "results": [
            {"url": r.url, "title": r.title, "excerpts": r.excerpts[:3]} for r in response.results
        ],
    }


def estimate_search_depth(entity_type: str, context_tier: str) -> dict[str, str]:
    """Report which search depth an entity would use, without searching.

    Useful for budgeting a run before spending anything.

    Args:
        entity_type: One of the clearance categories.
        context_tier: How the scene depicts it: neutral, unflattering, illegal.

    Returns:
        A dict with `mode`, one of turbo, fast, basic or advanced.
    """
    return {"mode": choose_mode(_entity_from("x", entity_type, context_tier))}


CLEARANCE_TOOLS = [
    FunctionTool(check_clearance_rule),
    FunctionTool(research_entity_on_the_web),
    FunctionTool(estimate_search_depth),
]

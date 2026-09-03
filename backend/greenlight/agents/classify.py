"""Phase 5 — verdict de clearance, ancré dans les sources.

Trois mécanismes, et ce sont eux qui font la différence entre ce pipeline et un
prompt « demande à un LLM si c'est risqué ».

**1. Le modèle ne juge que ce qu'il a lu.**
Il reçoit les extraits rapportés par Parallel et rien d'autre. Aucun appel à sa
mémoire d'entraînement, aucune connaissance implicite : un verdict de clearance
qui ne s'appuie pas sur une source vérifiable n'a aucune valeur devant un
assureur.

**2. Les citations sont vérifiées, pas crues.**
Toute URL citée qui ne figure pas dans les résultats de recherche est écartée.
Un verdict défavorable qui se retrouve sans aucune source valide retombe en
`UNRESOLVED` : une mise en cause non sourcée n'est pas un constat, c'est une
accusation.

**3. Existence et dépiction sont deux signaux distincts, combinés par une règle
explicite.**
Le modèle établit si les sources désignent une entité réelle *identifiable*.
Une règle déterministe applique ensuite le contexte de dépiction. C'est ce qui
permet à la même entité réelle de sortir `CLEAR` sur un plan de coupe et
`CHANGE_RECOMMENDED` quand un personnage y commet un délit — sans que le modèle
ait à arbitrer deux choses à la fois, et en laissant la règle lisible et
testable plutôt qu'enfouie dans un prompt.
"""

from __future__ import annotations

from greenlight.agents.gemini import GeminiClient
from greenlight.agents.research import ResearchResult
from greenlight.config import settings
from greenlight.models import (
    Citation,
    Classification,
    ContextTier,
    Entity,
    Finding,
    Verdict,
)

PROMPT_VERSION = "v1"

SYSTEM_INSTRUCTION = """\
You are a script clearance analyst producing a triage verdict on one entity \
named in a screenplay. You are not giving legal advice; you are deciding \
whether this entity needs a lawyer's attention before the film is shot.

You are given the entity, how the screenplay depicts it, and web search results.

**Judge only from the search results provided.** Do not use anything you \
happen to know about the entity. If the results do not establish something, it \
is not established.

Verdicts:

- `CLEAR` — no real-world counterpart was found, or the entity is real but its \
use here creates no meaningful exposure (incidental, nominative, or plainly \
fair use).
- `CAUTION` — a real counterpart plausibly exists and the use is worth a \
second look, but nothing in the sources ties this specific depiction to it.
- `CHANGE_RECOMMENDED` — the sources identify a real entity that a viewer \
would connect to this depiction, and the depiction could harm it. Renaming is \
cheaper than defending it.
- `LICENSE_REQUIRED` — the entity is a protected work or mark whose on-screen \
use needs permission regardless of how it is depicted (songs, artworks, \
published texts, logos shown as such).
- `UNRESOLVED` — the search did not settle the question. Use this rather than \
guessing. An honest gap is useful; a confident wrong answer is not.

`identifiable` must be true only when the sources point to a SPECIFIC real \
entity that a reasonable viewer would connect to this depiction — not merely \
that people or businesses share the name. A common surname with no matching \
profession, location or detail is NOT identifiable.

`cited_urls` must contain only URLs that appear in the search results given to \
you. Every verdict other than `CLEAR` needs at least one.

`rationale` is two sentences maximum, written for a producer, not a lawyer. \
Say what the sources show and what it means for the shoot.
"""


def build_prompt(entity: Entity, result: ResearchResult) -> str:
    scenes = sorted({o.scene_number for o in entity.occurrences})
    quotes = [o.quote for o in entity.occurrences if o.quote][:3]

    parts = [
        f"ENTITY: {entity.canonical_name}",
        f"CATEGORY: {entity.type.value}",
        f"ALSO WRITTEN AS: {', '.join(entity.aliases) or '(no variants)'}",
        f"APPEARS IN SCENES: {scenes}",
        f"WORST DEPICTION IN THE SCRIPT: {entity.worst_context.value}",
        "",
        "HOW THE SCREENPLAY USES IT:",
        *(f"  - {q}" for q in quotes),
        "",
        "SEARCH RESULTS:",
    ]

    if result.response is None or result.response.is_empty:
        parts.append(
            "  (none — the search returned no result for this entity)"
            if result.response is not None
            else "  (the search could not be completed)"
        )
    else:
        parts.append(result.response.as_context())

    return "\n".join(parts)


# --------------------------------------------------------------------------
# Garde-fou : une citation non vérifiable ne compte pas
# --------------------------------------------------------------------------


def verified_citations(classification: Classification, result: ResearchResult) -> list[Citation]:
    """Ne garde que les URL réellement rapportées par la recherche."""
    if result.response is None:
        return []
    by_url = {r.url: r for r in result.response.results}
    citations = []
    for url in classification.cited_urls:
        source = by_url.get(url)
        if source is None:
            continue  # URL inventée : écartée sans discussion
        citations.append(
            Citation(
                url=source.url,
                title=source.title,
                excerpt=source.text[:400],
                publish_date=source.publish_date,
            )
        )
    return citations


# --------------------------------------------------------------------------
# Règle de dépiction : le second signal
# --------------------------------------------------------------------------

# Verdicts déjà terminaux : rien à faire monter. `LICENSE_REQUIRED` tient au
# droit d'auteur, pas à la façon dont la scène traite l'œuvre ; `UNRESOLVED`
# décrit un manque d'information, qu'aggraver n'aurait aucun sens.
_TERMINAL = (Verdict.CHANGE_RECOMMENDED, Verdict.LICENSE_REQUIRED, Verdict.UNRESOLVED)


def apply_depiction(verdict: Verdict, identifiable: bool, context: ContextTier) -> Verdict:
    """Combine existence et dépiction.

    La condition `identifiable` est ce qui empêche la règle de tout repeindre en
    rouge : un nom banal dépeint dans un délit reste `CAUTION`, alors qu'une
    entité que les sources désignent nommément monte d'un cran.
    """
    if not identifiable or verdict in _TERMINAL:
        return verdict
    if context is ContextTier.ILLEGAL:
        return Verdict.CHANGE_RECOMMENDED
    if context is ContextTier.UNFLATTERING and verdict is Verdict.CLEAR:
        return Verdict.CAUTION
    return verdict


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------


def _finding(
    entity: Entity,
    draft_id: str,
    verdict: Verdict,
    confidence: float,
    rationale: str,
    citations: list[Citation] | None = None,
    escalated_from: Verdict | None = None,
    search_mode: str | None = None,
) -> Finding:
    return Finding(
        id=f"{draft_id}:{entity.id}",
        entity_id=entity.id,
        draft_id=draft_id,
        verdict=verdict,
        confidence=confidence,
        rationale=rationale,
        citations=citations or [],
        context_tier=entity.worst_context,
        escalated_from=escalated_from,
        search_mode=search_mode,
        prompt_version=PROMPT_VERSION,
    )


def classify_entity(
    result: ResearchResult,
    client: GeminiClient,
    draft_id: str,
    model: str | None = None,
) -> Finding:
    entity = result.entity

    # Tranché par règle en amont : aucune raison de payer un appel modèle.
    if result.rule is not None:
        return _finding(entity, draft_id, result.rule.verdict, 1.0, result.rule.rationale)

    if result.error is not None:
        return _finding(
            entity,
            draft_id,
            Verdict.UNRESOLVED,
            0.0,
            f"La recherche n'a pas abouti ({result.error}). Entité à vérifier à la main.",
            search_mode=result.spec.mode if result.spec else None,
        )

    mode = result.spec.mode if result.spec else None

    try:
        classification = client.structured(
            model=model or settings.model_classify,
            system=SYSTEM_INSTRUCTION,
            prompt=build_prompt(entity, result),
            schema=Classification,
        )
    except Exception as exc:
        return _finding(
            entity,
            draft_id,
            Verdict.UNRESOLVED,
            0.0,
            f"La classification a échoué ({type(exc).__name__}). Entité à vérifier à la main.",
            search_mode=mode,
        )

    citations = verified_citations(classification, result)
    verdict = classification.verdict
    rationale = classification.rationale

    # Une mise en cause sans source vérifiable n'est pas un constat.
    if verdict is not Verdict.CLEAR and not citations:
        return _finding(
            entity,
            draft_id,
            Verdict.UNRESOLVED,
            min(classification.confidence, 0.3),
            (
                f"{rationale} — aucune des sources citées n'a pu être vérifiée dans les "
                "résultats de recherche ; le verdict est laissé ouvert plutôt qu'affirmé."
            ),
            search_mode=mode,
        )

    escalated = apply_depiction(verdict, classification.identifiable, entity.worst_context)
    return _finding(
        entity,
        draft_id,
        escalated,
        classification.confidence,
        rationale,
        citations=citations,
        escalated_from=verdict if escalated is not verdict else None,
        search_mode=mode,
    )


def classify(
    results: list[ResearchResult],
    client: GeminiClient | None = None,
    draft_id: str = "draft-1",
    model: str | None = None,
) -> list[Finding]:
    client = client or GeminiClient()
    return [classify_entity(r, client, draft_id, model=model) for r in results]


# --------------------------------------------------------------------------
# Tri du rapport
# --------------------------------------------------------------------------

# Ce que le scénariste doit voir en premier. Un rapport trié par ordre
# alphabétique fait rater le seul point qui compte.
_SEVERITY = {
    Verdict.CHANGE_RECOMMENDED: 0,
    Verdict.LICENSE_REQUIRED: 1,
    Verdict.CAUTION: 2,
    Verdict.UNRESOLVED: 3,
    Verdict.CLEAR: 4,
}


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Trie le rapport tel qu'il doit être lu.

    Sévérité d'abord, évidemment. Mais à sévérité égale, un constat appuyé sur
    des sources passe avant une entité tranchée par règle : les deux sont « à
    changer », seul le premier demande un arbitrage. Sans ce départage, un
    numéro de téléphone corrigé par convention — confiance 1,0 — ouvrirait le
    rapport devant l'entité réellement risquée.
    """
    return sorted(
        findings,
        key=lambda f: (_SEVERITY[f.verdict], 0 if f.citations else 1, -f.confidence, f.entity_id),
    )

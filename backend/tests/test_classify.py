"""Phase 5 — verdicts.

Deux choses sont testées ici, et ce sont les deux qui font tenir le produit :
l'ancrage dans les sources (une mise en cause sans source vérifiable n'est pas
un constat) et la combinaison de l'existence et de la dépiction.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from greenlight.agents.classify import (
    apply_depiction,
    classify,
    classify_entity,
    sort_findings,
)
from greenlight.agents.gemini import GeminiClient
from greenlight.agents.research import ResearchResult
from greenlight.models import ContextTier, Entity, EntityType, Occurrence, Verdict
from greenlight.tools.parallel_search import SearchResponse, SearchResult
from greenlight.tools.queries import SearchSpec, pre_verdict

WIKI = "https://en.wikipedia.org/wiki/Black_Cat_Tavern"
NEWS = "https://news.test/black-cat"


def make(
    name: str,
    etype: EntityType = EntityType.BUSINESS,
    tier: ContextTier = ContextTier.NEUTRAL,
) -> Entity:
    return Entity(
        id=f"{etype.value.lower()}:{name.lower().replace(' ', '-')}",
        canonical_name=name,
        type=etype,
        occurrences=[
            Occurrence(scene_id="s1", scene_number=1, context_tier=tier, quote=f"{name} appears.")
        ],
    )


def researched(entity: Entity, urls: list[str] | None = None, mode: str = "advanced"):
    urls = [WIKI] if urls is None else urls
    return ResearchResult(
        entity=entity,
        spec=SearchSpec(objective="o", queries=["q"], mode=mode),  # type: ignore[arg-type]
        response=SearchResponse(
            search_id="s",
            results=[
                SearchResult(url=u, title=f"title of {u}", excerpts=["extrait"]) for u in urls
            ],
            mode=mode,
        ),
    )


def client_saying(**payload: Any) -> GeminiClient:
    body = {
        "verdict": "CAUTION",
        "confidence": 0.8,
        "rationale": "Les sources décrivent une entité réelle.",
        "cited_urls": [WIKI],
        "identifiable": False,
    }
    body.update(payload)
    client = GeminiClient(transport=lambda _: {"json": json.dumps(body), "usage": {}})
    client._fixtures.mode = "live"
    return client


# --- Ancrage dans les sources --------------------------------------------


def test_verdict_keeps_only_citations_that_exist_in_the_results():
    finding = classify_entity(
        researched(make("The Black Cat Tavern"), urls=[WIKI, NEWS]),
        client_saying(cited_urls=[WIKI, "https://inventee.test/page"]),
        "draft-1",
    )
    assert [c.url for c in finding.citations] == [WIKI]


def test_an_unsourced_accusation_falls_back_to_unresolved():
    """Toutes les citations inventées : le verdict défavorable ne tient pas."""
    finding = classify_entity(
        researched(make("The Black Cat Tavern")),
        client_saying(verdict="CHANGE_RECOMMENDED", cited_urls=["https://inventee.test/x"]),
        "draft-1",
    )
    assert finding.verdict is Verdict.UNRESOLVED
    assert finding.confidence <= 0.3
    assert not finding.citations


def test_clear_needs_no_citation():
    """Rien de réel trouvé : l'absence de source est justement le constat."""
    finding = classify_entity(
        researched(make("Zyxwv Tavern"), urls=[]),
        client_saying(verdict="CLEAR", cited_urls=[], rationale="Aucun équivalent réel trouvé."),
        "draft-1",
    )
    assert finding.verdict is Verdict.CLEAR


def test_citations_carry_title_and_excerpt_for_the_report():
    finding = classify_entity(researched(make("The Black Cat Tavern")), client_saying(), "draft-1")
    assert finding.citations[0].title
    assert finding.citations[0].excerpt


# --- Existence et dépiction ------------------------------------------------


def test_identified_entity_in_a_crime_scene_is_escalated():
    """Le piège : entité réelle nommément identifiée, scène de délit."""
    finding = classify_entity(
        researched(make("The Black Cat Tavern", tier=ContextTier.ILLEGAL)),
        client_saying(verdict="CAUTION", identifiable=True),
        "draft-1",
    )
    assert finding.verdict is Verdict.CHANGE_RECOMMENDED
    assert finding.escalated_from is Verdict.CAUTION


def test_common_name_in_a_crime_scene_is_not_escalated():
    """Le contre-exemple : nom banal, aucune source ne désigne quelqu'un de
    précis. La règle ne doit pas s'appliquer."""
    finding = classify_entity(
        researched(make("Daniel Reyes", EntityType.CHARACTER_NAME, ContextTier.ILLEGAL)),
        client_saying(verdict="CAUTION", identifiable=False),
        "draft-1",
    )
    assert finding.verdict is Verdict.CAUTION
    assert finding.escalated_from is None


def test_the_control_case_stays_clear():
    """Marque incontestablement réelle, usage incident et neutre. Un système qui
    la signale a appris « réel ⇒ risqué » au lieu de raisonner."""
    finding = classify_entity(
        researched(make("Coca-Cola", EntityType.PRODUCT_BRAND), mode="fast"),
        client_saying(verdict="CLEAR", identifiable=True, cited_urls=[WIKI]),
        "draft-1",
    )
    assert finding.verdict is Verdict.CLEAR
    assert finding.escalated_from is None


@pytest.mark.parametrize("verdict", [Verdict.LICENSE_REQUIRED, Verdict.UNRESOLVED])
def test_terminal_verdicts_are_left_alone(verdict):
    """Une licence tient au droit d'auteur, pas à la façon dont la scène traite
    l'œuvre ; `UNRESOLVED` décrit un manque, qu'aggraver n'a aucun sens."""
    assert apply_depiction(verdict, True, ContextTier.ILLEGAL) is verdict


def test_unflattering_depiction_moves_clear_to_caution():
    assert apply_depiction(Verdict.CLEAR, True, ContextTier.UNFLATTERING) is Verdict.CAUTION


def test_neutral_depiction_changes_nothing():
    assert apply_depiction(Verdict.CAUTION, True, ContextTier.NEUTRAL) is Verdict.CAUTION


# --- Court-circuits et robustesse ----------------------------------------


def test_rule_resolved_entity_skips_the_model_entirely():
    def must_not_be_called(_: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("le modèle a été appelé sur une entité tranchée par règle")

    entity = make("555-0147", EntityType.PHONE)
    client = GeminiClient(transport=must_not_be_called)
    client._fixtures.mode = "live"

    finding = classify_entity(
        ResearchResult(entity=entity, rule=pre_verdict(entity)), client, "draft-1"
    )
    assert finding.verdict is Verdict.CLEAR
    assert finding.confidence == 1.0


def test_failed_search_becomes_unresolved_not_a_guess():
    finding = classify_entity(
        ResearchResult(entity=make("The Black Cat Tavern"), error="RuntimeError: 502"),
        client_saying(),
        "draft-1",
    )
    assert finding.verdict is Verdict.UNRESOLVED
    assert "à vérifier à la main" in finding.rationale


def test_a_model_failure_becomes_unresolved():
    client = GeminiClient(transport=lambda _: {"json": "pas du json"})
    client._fixtures.mode = "live"

    finding = classify_entity(researched(make("The Black Cat Tavern")), client, "draft-1")
    assert finding.verdict is Verdict.UNRESOLVED


def test_finding_id_is_stable_per_draft_and_entity():
    entity = make("The Black Cat Tavern")
    a = classify_entity(researched(entity), client_saying(), "draft-1")
    b = classify_entity(researched(entity), client_saying(), "draft-1")
    assert a.id == b.id
    assert classify_entity(researched(entity), client_saying(), "draft-2").id != a.id


# --- Tri du rapport -------------------------------------------------------


def test_the_report_leads_with_what_must_change():
    results = [
        researched(make("Coca-Cola", EntityType.PRODUCT_BRAND)),
        researched(make("The Black Cat Tavern", tier=ContextTier.ILLEGAL)),
    ]
    findings = sort_findings(
        [
            classify_entity(results[0], client_saying(verdict="CLEAR"), "d1"),
            classify_entity(results[1], client_saying(verdict="CAUTION", identifiable=True), "d1"),
        ]
    )
    assert findings[0].verdict is Verdict.CHANGE_RECOMMENDED
    assert findings[-1].verdict is Verdict.CLEAR


def test_classify_returns_one_finding_per_entity():
    results = [researched(make(f"Business {i}")) for i in range(5)]
    assert len(classify(results, client_saying(), "d1")) == 5

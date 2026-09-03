"""Phase 8 — diff entre deux versions.

Un cache dont les conditions d'invalidation sont fausses est pire que pas de
cache : il ferait passer une entité redevenue risquée pour un dossier réglé.
Ces tests fixent exactement ce qui autorise la réutilisation d'un verdict.
"""

from __future__ import annotations

from greenlight.agents.classify import PROMPT_VERSION
from greenlight.agents.diff import plan
from greenlight.models import ContextTier, Entity, EntityType, Finding, Occurrence, Verdict


def make(
    name: str,
    etype: EntityType = EntityType.BUSINESS,
    tier: ContextTier = ContextTier.NEUTRAL,
) -> Entity:
    return Entity(
        id=f"{etype.value.lower()}:{name.lower().replace(' ', '-')}",
        canonical_name=name,
        type=etype,
        occurrences=[Occurrence(scene_id="s1", scene_number=1, context_tier=tier)],
    )


def finding_for(
    entity: Entity,
    verdict: Verdict = Verdict.CAUTION,
    prompt_version: str = PROMPT_VERSION,
) -> Finding:
    return Finding(
        id=f"draft-1:{entity.id}",
        entity_id=entity.id,
        draft_id="draft-1",
        verdict=verdict,
        confidence=0.8,
        rationale="…",
        context_tier=entity.worst_context,
        prompt_version=prompt_version,
    )


# --- Réutilisation --------------------------------------------------------


def test_an_untouched_entity_keeps_its_verdict():
    entity = make("Chicago Tribune", EntityType.PUBLICATION)
    diff = plan([entity], [finding_for(entity)], [entity], "draft-2")

    assert diff.to_analyze == []
    assert len(diff.reused) == 1
    assert diff.reused[0].verdict is Verdict.CAUTION


def test_a_reused_verdict_is_rekeyed_to_the_new_draft():
    entity = make("Chicago Tribune", EntityType.PUBLICATION)
    reused = plan([entity], [finding_for(entity)], [entity], "draft-2").reused[0]

    assert reused.draft_id == "draft-2"
    assert reused.id == f"draft-2:{entity.id}"
    assert reused.entity_id == entity.id


def test_a_spelling_variant_does_not_break_reuse():
    """L'identifiant vient du nom canonicalisé : « THE Chicago Tribune » et
    « Chicago Tribune » sont la même entité, et le verdict tient."""
    before = make("Chicago Tribune", EntityType.PUBLICATION)
    after = before.model_copy(update={"canonical_name": "the Chicago Tribune"})

    diff = plan([before], [finding_for(before)], [after], "draft-2")
    assert len(diff.reused) == 1


# --- Invalidation ---------------------------------------------------------


def test_a_renamed_entity_is_new_and_the_old_one_disappears():
    before = make("The Black Cat Tavern")
    after = make("The Paper Lantern")

    diff = plan([before], [finding_for(before)], [after], "draft-2")

    assert [e.canonical_name for e in diff.added] == ["The Paper Lantern"]
    assert [e.canonical_name for e in diff.removed] == ["The Black Cat Tavern"]
    assert diff.reused == []


def test_same_name_but_a_worse_depiction_is_reanalyzed():
    """Le cas que le diff ne doit surtout pas rater : le nom n'a pas bougé, mais
    la scène met désormais l'entité en cause. Réutiliser serait une faute."""
    before = make("Chicago Tribune", EntityType.PUBLICATION, ContextTier.NEUTRAL)
    after = make("Chicago Tribune", EntityType.PUBLICATION, ContextTier.ILLEGAL)

    diff = plan([before], [finding_for(before)], [after], "draft-2")

    assert [e.canonical_name for e in diff.recontextualized] == ["Chicago Tribune"]
    assert diff.reused == []


def test_a_depiction_that_softens_is_also_reanalyzed():
    """Dans l'autre sens aussi : le scénariste a droit à voir son drapeau tomber."""
    before = make("The Black Cat Tavern", tier=ContextTier.ILLEGAL)
    after = make("The Black Cat Tavern", tier=ContextTier.NEUTRAL)

    diff = plan([before], [finding_for(before, Verdict.CHANGE_RECOMMENDED)], [after], "draft-2")
    assert len(diff.recontextualized) == 1


def test_a_verdict_from_an_older_prompt_is_stale():
    entity = make("Chicago Tribune", EntityType.PUBLICATION)
    diff = plan([entity], [finding_for(entity, prompt_version="v0")], [entity], "draft-2")

    assert [e.canonical_name for e in diff.stale] == ["Chicago Tribune"]
    assert diff.reused == []


def test_an_entity_without_a_previous_verdict_is_reanalyzed():
    entity = make("Chicago Tribune", EntityType.PUBLICATION)
    diff = plan([entity], [], [entity], "draft-2")

    assert len(diff.stale) == 1


# --- Ce que le diff annonce -----------------------------------------------


def test_the_summary_states_what_was_actually_saved():
    unchanged = [make(f"Business {i}") for i in range(9)]
    changed = make("The Paper Lantern")
    findings = [finding_for(e) for e in unchanged]

    diff = plan(unchanged, findings, [*unchanged, changed], "draft-2")

    assert len(diff.to_analyze) == 1
    assert diff.unchanged_count == 9
    assert "1 entités à réanalyser sur 10" in diff.summary()
    assert "90 %" in diff.summary()


def test_an_empty_draft_reports_nothing_rather_than_dividing_by_zero():
    assert "Aucune entité" in plan([], [], [], "draft-2").summary()


def test_a_first_pass_with_no_history_reanalyzes_everything():
    entities = [make("A"), make("B")]
    diff = plan([], [], entities, "draft-1")

    assert len(diff.to_analyze) == 2
    assert diff.reused == []

import pytest

from greenlight.models import ContextTier, Entity, EntityType, Occurrence, Verdict
from greenlight.tools.queries import build_search, choose_mode, pre_verdict


def make(name: str, etype: EntityType, tier: ContextTier = ContextTier.NEUTRAL) -> Entity:
    return Entity(
        id="e1",
        canonical_name=name,
        type=etype,
        occurrences=[Occurrence(scene_id="s1", scene_number=1, context_tier=tier)],
    )


# --- Pré-verdicts déterministes : aucun appel réseau ----------------------


@pytest.mark.parametrize("number", ["555-0147", "555 0147", "(212) 555-0100"])
def test_fictional_phone_range_is_clear(number):
    verdict = pre_verdict(make(number, EntityType.PHONE))
    assert verdict is not None
    assert verdict.verdict is Verdict.CLEAR


def test_real_looking_phone_must_change():
    verdict = pre_verdict(make("312-555-8890", EntityType.PHONE))
    assert verdict is not None
    assert verdict.verdict is Verdict.CHANGE_RECOMMENDED


def test_rfc2606_domain_is_clear():
    verdict = pre_verdict(make("dreyes@example.com", EntityType.URL_EMAIL))
    assert verdict is not None
    assert verdict.verdict is Verdict.CLEAR


def test_neutral_government_agency_is_clear():
    verdict = pre_verdict(make("FDA", EntityType.GOVERNMENT_AGENCY))
    assert verdict is not None
    assert verdict.verdict is Verdict.CLEAR


def test_agency_in_illegal_context_still_needs_research():
    entity = make("FDA", EntityType.GOVERNMENT_AGENCY, ContextTier.ILLEGAL)
    assert pre_verdict(entity) is None


def test_business_always_needs_research():
    assert pre_verdict(make("The Black Cat Tavern", EntityType.BUSINESS)) is None


# --- Routage par niveau de risque ----------------------------------------


def test_neutral_business_uses_cheap_mode():
    assert choose_mode(make("Acme Corp", EntityType.BUSINESS)) == "fast"


def test_illegal_context_escalates_to_advanced():
    entity = make("The Black Cat Tavern", EntityType.BUSINESS, ContextTier.ILLEGAL)
    assert choose_mode(entity) == "advanced"


def test_high_stakes_category_always_advanced():
    assert choose_mode(make("Sweet Child O' Mine", EntityType.SONG)) == "advanced"


# --- Construction des requêtes -------------------------------------------


def test_search_spec_is_type_aware():
    spec = build_search(make("Sweet Child O' Mine", EntityType.SONG))
    assert "rights holders" in spec.objective or "publisher" in spec.objective.lower()
    assert 1 <= len(spec.queries) <= 3
    assert spec.mode == "advanced"


def test_character_search_uses_scene_hint():
    spec = build_search(
        make("Marcus Webb", EntityType.CHARACTER_NAME), scene_hint="emergency room doctor"
    )
    assert "emergency room doctor" in spec.objective
    assert any("Marcus Webb" in q for q in spec.queries)


def test_queries_are_quoted_for_exact_match():
    spec = build_search(make("Mercy General Hospital", EntityType.INSTITUTION))
    assert all('"Mercy General Hospital"' in q for q in spec.queries[:1])

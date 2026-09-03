"""Phase 2 — extraction.

Le transport Gemini est injecté : ces tests valident le contrat et les
garde-fous du pipeline, pas la qualité du modèle. Ils tournent hors ligne et ne
consomment aucun token. La qualité du modèle, elle, se mesure contre
`samples/EXPECTED.md` lors d'un run marqué `live`.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from greenlight.agents.extract import (
    SYSTEM_INSTRUCTION,
    appears_in,
    build_prompt,
    extract_draft,
    extract_scene,
)
from greenlight.agents.gemini import GeminiClient, GeminiError
from greenlight.models import ContextTier, Draft, EntityType, Scene
from greenlight.tools.fixtures import FixtureMiss

SCENE = Scene(
    id="d1-s4",
    number=4,
    heading="INT. THE BLACK CAT TAVERN - NIGHT",
    int_ext="INT",
    location="THE BLACK CAT TAVERN",
    time_of_day="NIGHT",
    action="A can of Coca-Cola sweats on the windowsill. DANIEL slides a bag across the bar.",
    dialogue=["DANIEL: Tell Webb it's the last one.", "MARCUS: Call 312-555-8890 when it's done."],
    characters=["DANIEL", "MARCUS"],
)


def transport_returning(entities: list[dict[str, Any]], usage: dict[str, int] | None = None):
    """Faux transport : rend la charge utile qu'aurait rendue le modèle."""

    def _transport(request: dict[str, Any]) -> dict[str, Any]:
        return {
            "json": json.dumps({"entities": entities}),
            "usage": usage or {"prompt_tokens": 800, "output_tokens": 120},
        }

    return _transport


def client_returning(entities: list[dict[str, Any]], **kwargs) -> GeminiClient:
    client = GeminiClient(transport=transport_returning(entities, **kwargs))
    # Les fixtures sont forcées en replay par conftest ; on veut ici que le
    # faux transport soit réellement appelé.
    client._fixtures.mode = "live"
    return client


# --- Prompt ---------------------------------------------------------------


def test_prompt_carries_heading_action_and_dialogue():
    prompt = build_prompt(SCENE)
    assert "THE BLACK CAT TAVERN" in prompt
    assert "Coca-Cola" in prompt
    assert "312-555-8890" in prompt


def test_system_instruction_defines_the_three_context_tiers():
    for tier in ("neutral", "unflattering", "illegal"):
        assert tier in SYSTEM_INSTRUCTION


# --- Contrat de sortie structurée -----------------------------------------


def test_extraction_returns_typed_entities():
    client = client_returning(
        [
            {
                "name": "The Black Cat Tavern",
                "type": "BUSINESS",
                "context_tier": "illegal",
                "quote": "DANIEL slides a bag across the bar.",
            },
            {
                "name": "Coca-Cola",
                "type": "PRODUCT_BRAND",
                "context_tier": "neutral",
                "quote": "A can of Coca-Cola sweats on the windowsill.",
            },
        ]
    )
    result = extract_scene(SCENE, client)

    assert [e.name for e in result.entities] == ["The Black Cat Tavern", "Coca-Cola"]
    assert result.entities[0].type is EntityType.BUSINESS
    assert result.entities[0].context_tier is ContextTier.ILLEGAL
    # Le cas témoin : entité incontestablement réelle, dépiction neutre.
    assert result.entities[1].context_tier is ContextTier.NEUTRAL
    assert not result.dropped


def test_malformed_model_output_raises_rather_than_guessing():
    client = GeminiClient(transport=lambda _: {"json": "not json at all"})
    client._fixtures.mode = "live"
    with pytest.raises(GeminiError):
        extract_scene(SCENE, client)


def test_unknown_entity_type_is_rejected():
    client = client_returning(
        [{"name": "Coca-Cola", "type": "SOFT_DRINK", "context_tier": "neutral", "quote": ""}]
    )
    with pytest.raises(GeminiError):
        extract_scene(SCENE, client)


# --- Garde-fou anti-hallucination -----------------------------------------


def test_entity_absent_from_the_scene_is_dropped_before_any_search():
    client = client_returning(
        [
            {"name": "Coca-Cola", "type": "PRODUCT_BRAND", "context_tier": "neutral", "quote": ""},
            # Jamais écrit par le scénariste : ne doit pas atteindre le fan-out.
            {"name": "Pepsi", "type": "PRODUCT_BRAND", "context_tier": "neutral", "quote": ""},
        ]
    )
    result = extract_scene(SCENE, client)

    assert [e.name for e in result.entities] == ["Coca-Cola"]
    assert [e.name for e in result.dropped] == ["Pepsi"]


@pytest.mark.parametrize(
    "name",
    ["coca cola", "COCA-COLA", "(312) 555 8890", "the black cat tavern"],
)
def test_guard_tolerates_punctuation_and_case_variants(name):
    haystack = f"{SCENE.heading}\n{SCENE.action}\n" + "\n".join(SCENE.dialogue)
    assert appears_in(name, haystack)


def test_guard_rejects_an_empty_name():
    assert not appears_in("   ", "anything")


# --- Résilience et comptage -----------------------------------------------


def test_a_failing_scene_does_not_take_down_the_draft():
    def flaky(request: dict[str, Any]) -> dict[str, Any]:
        if "SCENE 1" in request["prompt"]:
            raise RuntimeError("timeout côté modèle")
        return {"json": json.dumps({"entities": []}), "usage": {}}

    client = GeminiClient(transport=flaky)
    client._fixtures.mode = "live"
    draft = Draft(
        id="d1",
        version=1,
        source_path="",
        fmt="fountain",
        scenes=[
            Scene(id="d1-s1", number=1, heading="INT. A - DAY"),
            Scene(id="d1-s2", number=2, heading="INT. B - DAY"),
        ],
    )

    results = extract_draft(draft, client)
    assert len(results) == 2
    assert results[0].error is not None and "timeout" in results[0].error
    assert results[1].error is None


def test_token_usage_is_measured_not_estimated():
    client = client_returning(
        [{"name": "Coca-Cola", "type": "PRODUCT_BRAND", "context_tier": "neutral", "quote": ""}],
        usage={"prompt_tokens": 1234, "output_tokens": 56},
    )
    extract_scene(SCENE, client)

    summary = client.usage_summary()
    assert summary["calls"] == 1
    assert summary["prompt_tokens"] == 1234
    assert summary["output_tokens"] == 56
    # Aucun prix renseigné dans l'environnement : aucun montant annoncé.
    assert "cost_usd" not in summary


def test_replay_mode_never_reaches_the_transport():
    """Garantie de coût : en replay, une fixture manquante échoue bruyamment
    plutôt que de retomber discrètement sur un appel facturé."""

    def must_not_be_called(_: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("le transport a été appelé en mode replay")

    client = GeminiClient(transport=must_not_be_called)  # replay forcé par conftest
    with pytest.raises(FixtureMiss):
        extract_scene(SCENE, client)
    assert client.usage_summary()["prompt_tokens"] == 0

"""Phases 1 → 3 de bout en bout, sur le vrai scénario de démonstration.

Le transport Gemini est simulé, mais tout le reste est réel : le fichier
`seventeen_minutes.fountain`, le parser, le garde-fou, la canonicalisation et le
routage de recherche. Ce test protège la jonction entre les phases — l'endroit
où une régression casse la démo sans casser aucun test unitaire.
"""

from __future__ import annotations

import json
import re
from typing import Any

from greenlight.agents.gemini import GeminiClient
from greenlight.models import ContextTier, EntityType, Verdict
from greenlight.pipeline import report, run_extraction
from greenlight.tools.queries import choose_mode, pre_verdict

# Ce que le modèle est censé rendre sur ce scénario, d'après samples/EXPECTED.md.
# Le faux transport ne rend une entité que si elle apparaît réellement dans la
# scène demandée : la scène qui la porte n'est donc pas codée en dur ici.
LANDMINES: list[tuple[str, EntityType, ContextTier]] = [
    ("The Black Cat Tavern", EntityType.BUSINESS, ContextTier.ILLEGAL),
    ("Marcus Webb", EntityType.CHARACTER_NAME, ContextTier.ILLEGAL),
    ("Mercy General Hospital", EntityType.INSTITUTION, ContextTier.ILLEGAL),
    ("312-555-8890", EntityType.PHONE, ContextTier.NEUTRAL),
    ("555-0147", EntityType.PHONE, ContextTier.NEUTRAL),
    ("Sweet Child O' Mine", EntityType.SONG, ContextTier.NEUTRAL),
    ("Nighthawks", EntityType.ARTWORK, ContextTier.NEUTRAL),
    ("Chicago Tribune", EntityType.PUBLICATION, ContextTier.NEUTRAL),
    ("7XKD429", EntityType.LICENSE_PLATE, ContextTier.NEUTRAL),
    ("4400 North Broadway", EntityType.ADDRESS, ContextTier.NEUTRAL),
    ("Daniel Reyes", EntityType.CHARACTER_NAME, ContextTier.ILLEGAL),
    ("Coca-Cola", EntityType.PRODUCT_BRAND, ContextTier.NEUTRAL),
    ("dreyes@example.com", EntityType.URL_EMAIL, ContextTier.NEUTRAL),
    ("FDA", EntityType.GOVERNMENT_AGENCY, ContextTier.NEUTRAL),
    ("CPD", EntityType.GOVERNMENT_AGENCY, ContextTier.NEUTRAL),
]

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _scripted_transport(request: dict[str, Any]) -> dict[str, Any]:
    """Rend les entités du catalogue effectivement présentes dans le prompt."""
    haystack = _NON_ALNUM.sub("", request["prompt"].lower())
    entities = [
        {"name": name, "type": etype.value, "context_tier": tier.value, "quote": name}
        for name, etype, tier in LANDMINES
        if _NON_ALNUM.sub("", name.lower()) in haystack
    ]
    # Une hallucination volontaire, jamais écrite dans le scénario : le
    # garde-fou doit l'écarter avant tout appel à Parallel.
    entities.append(
        {"name": "Pepsi Max", "type": "PRODUCT_BRAND", "context_tier": "neutral", "quote": ""}
    )
    return {
        "json": json.dumps({"entities": entities}),
        "usage": {"prompt_tokens": 900, "output_tokens": 140},
    }


def scripted_client() -> GeminiClient:
    client = GeminiClient(transport=_scripted_transport)
    client._fixtures.mode = "live"  # le faux transport remplace le réseau
    return client


def test_end_to_end_extraction(sample_script):
    run = run_extraction(sample_script, scripted_client())

    assert len(run.draft.scenes) > 1
    assert not run.failed_scenes
    assert run.usage["calls"] == len(run.draft.scenes)

    found = {e.canonical_name for e in run.entities}
    missing = [name for name, _, _ in LANDMINES if name not in found]
    assert not missing, f"pièges perdus entre les phases : {missing}"


def test_hallucination_never_reaches_the_search_queue(sample_script):
    run = run_extraction(sample_script, scripted_client())

    assert "Pepsi Max" not in {e.canonical_name for e in run.entities}
    assert run.dropped_count == len(run.draft.scenes)


def test_recurring_entity_is_deduplicated_across_scenes(sample_script):
    run = run_extraction(sample_script, scripted_client())

    tavern = [e for e in run.entities if e.canonical_name == "The Black Cat Tavern"]
    assert len(tavern) == 1, "l'entité doit être unique, quel que soit le nombre de scènes"
    assert len(tavern[0].occurrences) >= 1


def test_deterministic_rules_take_entities_out_of_the_billed_queue(sample_script):
    run = run_extraction(sample_script, scripted_client())
    free = {e.canonical_name: pre_verdict(e).verdict for e in run.resolved_without_search()}

    assert free.get("555-0147") is Verdict.CLEAR
    assert free.get("dreyes@example.com") is Verdict.CLEAR
    assert free.get("FDA") is Verdict.CLEAR
    # Hors de la plage fictive : tranché sans recherche, mais à corriger.
    assert free.get("312-555-8890") is Verdict.CHANGE_RECOMMENDED


def test_depiction_drives_the_search_budget(sample_script):
    """Le cas témoin et le piège coûtent volontairement des montants différents."""
    run = run_extraction(sample_script, scripted_client())
    by_name = {e.canonical_name: e for e in run.entities}

    assert choose_mode(by_name["The Black Cat Tavern"]) == "advanced"
    assert choose_mode(by_name["Coca-Cola"]) == "fast"


def test_report_states_measured_numbers(sample_script):
    run = run_extraction(sample_script, scripted_client())
    text = report(run)

    assert "Entités" in text and "Sans recherche" in text
    assert str(len(run.draft.scenes)) in text
    # Aucun prix Gemini renseigné : le compte-rendu parle en tokens, pas en dollars.
    assert "cost_usd" not in text

"""Phases 1 → 3 de bout en bout, sur le vrai scénario de démonstration.

Le transport Gemini est simulé, mais tout le reste est réel : le fichier
`seventeen_minutes.fountain`, le parser, le garde-fou, la canonicalisation et le
routage de recherche. Ce test protège la jonction entre les phases — l'endroit
où une régression casse la démo sans casser aucun test unitaire.
"""

from __future__ import annotations

import json
import re
import threading
from typing import Any

from greenlight.agents.gemini import GeminiClient
from greenlight.models import ContextTier, EntityType, Verdict
from greenlight.pipeline import clearance_report, report, run_clearance, run_extraction
from greenlight.tools.parallel_search import ParallelSearch, SearchResponse, SearchResult
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


# --------------------------------------------------------------------------
# Phases 1 → 5 : la passe complète, confrontée à samples/EXPECTED.md
# --------------------------------------------------------------------------

# Ce que le modèle de classification est censé rendre entité par entité, en ne
# lisant que les sources. `identifiable` est le signal qui autorise la règle de
# dépiction à faire monter le verdict — c'est lui qui sépare « Marcus Webb,
# médecin réel identifiable, qui deale » de « Daniel Reyes, nom banal ».
RAW_CLASSIFICATIONS: dict[str, tuple[str, bool]] = {
    "The Black Cat Tavern": ("CAUTION", True),
    "Marcus Webb": ("CAUTION", True),
    "Mercy General Hospital": ("CAUTION", True),
    "Sweet Child O' Mine": ("LICENSE_REQUIRED", True),
    "Nighthawks": ("LICENSE_REQUIRED", True),
    "Chicago Tribune": ("CAUTION", True),
    "7XKD429": ("CAUTION", False),
    "4400 North Broadway": ("CAUTION", True),
    "Daniel Reyes": ("CAUTION", False),
    "Coca-Cola": ("CLEAR", True),
    # Les noms introduits par la réécriture. Ils sont inventés : une recherche
    # réelle ne leur trouve aucun équivalent, donc `CLEAR`. C'est exactement ce
    # que le mode diff doit montrer — renommer fait tomber le drapeau.
    "The Paper Lantern": ("CLEAR", False),
    "Saint Odile Medical Center": ("CLEAR", False),
    "Riverton County Courthouse": ("CLEAR", False),
}

# La table de samples/EXPECTED.md, vérifiée à la main. Quand le pipeline s'en
# écarte, c'est le pipeline qui a tort.
EXPECTED_VERDICTS: dict[str, Verdict] = {
    "The Black Cat Tavern": Verdict.CHANGE_RECOMMENDED,
    "Marcus Webb": Verdict.CHANGE_RECOMMENDED,
    "Mercy General Hospital": Verdict.CHANGE_RECOMMENDED,
    "312-555-8890": Verdict.CHANGE_RECOMMENDED,
    "555-0147": Verdict.CLEAR,
    "Sweet Child O' Mine": Verdict.LICENSE_REQUIRED,
    "Nighthawks": Verdict.LICENSE_REQUIRED,
    "Chicago Tribune": Verdict.CAUTION,
    "7XKD429": Verdict.CAUTION,
    "4400 North Broadway": Verdict.CAUTION,
    "Daniel Reyes": Verdict.CAUTION,
    "CPD": Verdict.CLEAR,
    "Coca-Cola": Verdict.CLEAR,
    "dreyes@example.com": Verdict.CLEAR,
    "FDA": Verdict.CLEAR,
}


class ScriptedSearch(ParallelSearch):
    """Rend une source plausible et traçable par entité recherchée."""

    def __init__(self) -> None:
        super().__init__()
        self.performed: list[str] = []
        self._performed_lock = threading.Lock()

    def search(self, objective, search_queries, mode=None):  # type: ignore[override]
        with self._performed_lock:
            self.performed.append(search_queries[0])
        slug = re.sub(r"[^a-z0-9]+", "-", search_queries[0].lower()).strip("-")
        return SearchResponse(
            search_id="scripted",
            results=[
                SearchResult(
                    url=f"https://sources.test/{slug}",
                    title=f"Source for {search_queries[0]}",
                    excerpts=["Extrait rapporté par la recherche."],
                )
            ],
            mode=mode or "fast",
        )


def _classification_for(prompt: str) -> dict[str, Any]:
    name = prompt.split("ENTITY: ", 1)[1].split("\n", 1)[0].strip()
    verdict, identifiable = RAW_CLASSIFICATIONS.get(name, ("UNRESOLVED", False))
    urls = re.findall(r"https://\S+", prompt)
    return {
        "verdict": verdict,
        "confidence": 0.85,
        "rationale": f"Les sources décrivent {name}.",
        # Seules des URL réellement présentes dans les résultats : c'est ce que
        # le garde-fou de citations attend d'un modèle honnête.
        "cited_urls": urls[:1] if verdict != "CLEAR" else [],
        "identifiable": identifiable,
    }


def _dual_transport(request: dict[str, Any]) -> dict[str, Any]:
    """Un seul client Gemini sert les phases 2 et 5 : on aiguille sur le schéma."""
    if request["schema"] == "Classification":
        body = _classification_for(request["prompt"])
    else:
        body = json.loads(_scripted_transport(request)["json"])
    return {"json": json.dumps(body), "usage": {"prompt_tokens": 900, "output_tokens": 140}}


def clearance_client() -> GeminiClient:
    client = GeminiClient(transport=_dual_transport)
    client._fixtures.mode = "live"
    return client


def full_run(sample_script, search: ScriptedSearch | None = None):
    return run_clearance(
        sample_script, clearance_client(), search or ScriptedSearch(), max_workers=4
    )


def test_every_hand_verified_verdict_is_reproduced(sample_script):
    run = full_run(sample_script)
    by_name = {
        next(e.canonical_name for e in run.extraction.entities if e.id == f.entity_id): f.verdict
        for f in run.findings
    }

    mismatches = {
        name: (by_name.get(name), expected)
        for name, expected in EXPECTED_VERDICTS.items()
        if by_name.get(name) is not expected
    }
    assert not mismatches, f"écarts avec samples/EXPECTED.md : {mismatches}"


def test_depiction_rule_moves_exactly_the_entities_it_should(sample_script):
    run = full_run(sample_script)
    escalated = {
        next(e.canonical_name for e in run.extraction.entities if e.id == f.entity_id)
        for f in run.escalated
    }
    # Identifiables et mises en scène dans un délit — et elles seules.
    assert escalated == {"The Black Cat Tavern", "Marcus Webb", "Mercy General Hospital"}


def test_the_control_case_survives_the_whole_pipeline(sample_script):
    """Coca-Cola traverse extraction, recherche et classification sans être
    signalée. C'est la preuve que le système raisonne sur la dépiction au lieu
    d'avoir appris « réel ⇒ risqué »."""
    run = full_run(sample_script)
    coke = next(
        f
        for f in run.findings
        if next(e.canonical_name for e in run.extraction.entities if e.id == f.entity_id)
        == "Coca-Cola"
    )
    assert coke.verdict is Verdict.CLEAR
    assert coke.escalated_from is None


def test_flagged_entities_all_carry_a_verifiable_source(sample_script):
    """Aucune mise en cause sans source : c'est la règle qui rend le rapport
    opposable plutôt que déclaratif."""
    run = full_run(sample_script)
    unsourced = [
        f.entity_id
        for f in run.flagged
        if f.search_mode is not None and not f.citations and f.verdict is not Verdict.UNRESOLVED
    ]
    assert not unsourced


def test_rule_resolved_entities_cost_nothing(sample_script):
    search = ScriptedSearch()
    run = full_run(sample_script, search)
    rule_resolved = run.research.skipped_by_rule

    assert len(rule_resolved) == 5
    # Une recherche par entité facturable, pas une de plus.
    assert len(search.performed) == len(run.extraction.entities) - len(rule_resolved)
    # Et pas un appel modèle pour les entités déjà tranchées.
    assert run.gemini_usage["calls"] == len(run.extraction.scenes) + len(search.performed)


def test_replay_mode_reports_no_spend(sample_script):
    """Le harnais de fixtures est en replay : la passe complète est rejouable
    autant de fois que nécessaire sans consommer un crédit."""
    run = full_run(sample_script)

    assert run.search_usage["fixture_mode"] == "replay"
    assert run.search_usage["requests"] == 0
    assert run.search_usage["cost_usd"] == 0.0


def test_clearance_report_leads_with_what_must_change(sample_script):
    text = clearance_report(full_run(sample_script))

    assert "Verdicts" in text
    assert text.index("[CHANGE_RECOMMENDED]") < text.index("[CLEAR]")
    assert "remonté depuis" in text


# --------------------------------------------------------------------------
# Phase 8 : la réécriture, de bout en bout
# --------------------------------------------------------------------------

# Ce que la version 2 introduit. Le reste du catalogue est inchangé, donc les
# verdicts correspondants doivent être repris sans nouvelle recherche.
V2_ENTITIES: list[tuple[str, EntityType, ContextTier]] = [
    ("The Paper Lantern", EntityType.BUSINESS, ContextTier.ILLEGAL),
    ("Saint Odile Medical Center", EntityType.INSTITUTION, ContextTier.ILLEGAL),
    ("312-555-0188", EntityType.PHONE, ContextTier.NEUTRAL),
    ("Riverton County Courthouse", EntityType.INSTITUTION, ContextTier.NEUTRAL),
]

# Le titre est le même dans les deux versions ; c'est la scène qui change. Le
# stub relit donc le texte au lieu de coder la version en dur, exactement comme
# le modèle le ferait : la v2 fait du journal l'instrument d'un faux.
CONTEXT_OVERRIDES: dict[str, tuple[str, ContextTier]] = {
    "Chicago Tribune": ("forged", ContextTier.ILLEGAL),
}


def v2_client() -> GeminiClient:
    """Même transport, avec le catalogue élargi aux entités de la version 2."""
    catalogue = LANDMINES + V2_ENTITIES

    def transport(request: dict[str, Any]) -> dict[str, Any]:
        if request["schema"] == "Classification":
            return {
                "json": json.dumps(_classification_for(request["prompt"])),
                "usage": {"prompt_tokens": 900, "output_tokens": 140},
            }
        prompt = request["prompt"].lower()
        haystack = _NON_ALNUM.sub("", prompt)
        seen, entities = set(), []
        for name, etype, tier in catalogue:
            if name in seen or _NON_ALNUM.sub("", name.lower()) not in haystack:
                continue
            seen.add(name)
            trigger = CONTEXT_OVERRIDES.get(name)
            if trigger is not None and trigger[0] in prompt:
                tier = trigger[1]
            entities.append(
                {"name": name, "type": etype.value, "context_tier": tier.value, "quote": name}
            )
        return {
            "json": json.dumps({"entities": entities}),
            "usage": {"prompt_tokens": 900, "output_tokens": 140},
        }

    client = GeminiClient(transport=transport)
    client._fixtures.mode = "live"
    return client


def rewrite_run(sample_script, sample_script_v2, search: ScriptedSearch | None = None):
    first = run_clearance(sample_script, v2_client(), ScriptedSearch(), max_workers=4)
    second = run_clearance(
        sample_script_v2,
        v2_client(),
        search or ScriptedSearch(),
        draft_id="draft-2",
        max_workers=4,
        previous=first,
    )
    return first, second


def test_a_rewrite_only_reanalyzes_what_actually_moved(sample_script, sample_script_v2):
    search = ScriptedSearch()
    first, second = rewrite_run(sample_script, sample_script_v2, search)

    names = {e.canonical_name for e in second.diff.to_analyze}
    assert names == {
        "The Paper Lantern",  # renommé
        "Saint Odile Medical Center",  # renommé
        "312-555-0188",  # numéro corrigé
        "Riverton County Courthouse",  # scène ajoutée
        "Chicago Tribune",  # même nom, dépiction devenue délictueuse
    }
    # Une recherche pour les seules entités facturables de ce sous-ensemble.
    assert len(search.performed) < len(first.extraction.entities)


def test_the_rewrite_keeps_every_other_verdict(sample_script, sample_script_v2):
    _, second = rewrite_run(sample_script, sample_script_v2)

    reused = {f.entity_id for f in second.diff.reused}
    assert "product_brand:coca-cola" in reused
    assert "song:sweet-child-o-mine" in reused
    # Un verdict repris est réattribué à la nouvelle version, pas laissé sur
    # l'ancienne : sinon le rapport v2 citerait des identifiants de v1.
    assert all(f.draft_id == "draft-2" for f in second.diff.reused)


def test_a_recontextualized_entity_is_never_silently_reused(sample_script, sample_script_v2):
    """Chicago Tribune garde son nom mais devient l'instrument d'un faux. Reprendre
    son verdict de v1 laisserait passer un risque réel."""
    _, second = rewrite_run(sample_script, sample_script_v2)

    assert "Chicago Tribune" in {e.canonical_name for e in second.diff.recontextualized}
    assert "publication:chicago-tribune" not in {f.entity_id for f in second.diff.reused}


def test_the_renamed_entities_are_gone_from_the_new_report(sample_script, sample_script_v2):
    _, second = rewrite_run(sample_script, sample_script_v2)

    removed = {e.canonical_name for e in second.diff.removed}
    assert {"The Black Cat Tavern", "Mercy General Hospital", "312-555-8890"} <= removed


def test_the_report_states_the_saving(sample_script, sample_script_v2):
    _, second = rewrite_run(sample_script, sample_script_v2)
    text = clearance_report(second)

    assert "Diff" in text
    assert "verdicts repris de la version précédente" in text
    assert "% de la recherche évitée" in text

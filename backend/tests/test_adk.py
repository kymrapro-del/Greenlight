"""Couche ADK.

Le test qui porte tout est celui de l'équivalence : l'agent ADK et la
bibliothèque doivent rendre exactement le même rapport. Sans lui, les deux
chemins divergeraient en silence et l'un des deux finirait par mentir.

Aucun réseau, aucun token : les collaborateurs sont injectés.
"""

from __future__ import annotations

import pytest

from greenlight.adk.agents import ClearanceDeps, build_clearance_agent, build_phases
from greenlight.adk.runner import run_clearance_agent
from greenlight.adk.tools import CLEARANCE_TOOLS, check_clearance_rule, estimate_search_depth
from greenlight.models import Verdict
from greenlight.pipeline import run_clearance

from .test_pipeline import ScriptedSearch, v2_client


def adk_run(script, **kwargs):
    return run_clearance_agent(script, client=v2_client(), search=ScriptedSearch(), **kwargs)


def library_run(script, **kwargs):
    return run_clearance(script, v2_client(), ScriptedSearch(), **kwargs)


# --- Équivalence des deux chemins ----------------------------------------


def test_the_agent_and_the_library_agree_verdict_for_verdict(sample_script):
    """Deux runtimes, un seul comportement. C'est la garantie qui autorise à
    déployer l'un et à développer sur l'autre."""
    through_adk = adk_run(sample_script)
    through_library = library_run(sample_script)

    assert [(f.entity_id, f.verdict) for f in through_adk.findings] == [
        (f.entity_id, f.verdict) for f in through_library.findings
    ]


def test_both_paths_report_the_same_entities(sample_script):
    assert {e.id for e in adk_run(sample_script).extraction.entities} == {
        e.id for e in library_run(sample_script).extraction.entities
    }


def test_the_agent_preserves_the_depiction_rule(sample_script):
    run = adk_run(sample_script)
    escalated = {
        next(e.canonical_name for e in run.extraction.entities if e.id == f.entity_id)
        for f in run.escalated
    }
    assert escalated == {"The Black Cat Tavern", "Marcus Webb", "Mercy General Hospital"}


def test_the_agent_runs_the_diff(sample_script, sample_script_v2):
    first = adk_run(sample_script)
    second = adk_run(sample_script_v2, draft_id="draft-2", previous=first)

    assert second.diff is not None
    assert second.diff.reused
    # Le rapport final réintègre les verdicts repris : rien ne se perd.
    assert len(second.findings) == len(second.extraction.entities)


def test_suggestions_are_off_unless_asked(sample_script):
    assert not adk_run(sample_script).verified_replacements
    assert adk_run(sample_script, suggest=True).verified_replacements


# --- Composition de l'agent ----------------------------------------------


def test_the_pipeline_is_a_workflow_of_eight_phases():
    """`Workflow` et non `SequentialAgent` : ce dernier est déprécié depuis
    l'ADK 2.8, et le graphe permettra de paralléliser sans tout réécrire."""
    agent = build_clearance_agent(ClearanceDeps())
    assert [phase.name for phase in build_phases(ClearanceDeps())] == [
        "ingest",
        "extract",
        "canonicalize",
        "diff",
        "research",
        "classify",
        "suggest",
        "report",
    ]
    # Sept transitions entre phases, plus l'amorce depuis START.
    assert len(agent.edges) == 8


def test_the_diff_runs_before_the_research():
    """L'ordre n'est pas celui des numéros de phase : le diff décide de ce qu'il
    reste à chercher, donc il doit passer avant la recherche."""
    names = [phase.name for phase in build_phases(ClearanceDeps())]
    assert names.index("diff") < names.index("research")


def test_each_phase_reports_progress(sample_script):
    seen: list[tuple[str, str]] = []
    run_clearance_agent(
        sample_script,
        client=v2_client(),
        search=ScriptedSearch(),
        on_event=lambda a, t: seen.append((a, t)),
    )
    assert [author for author, _ in seen] == [
        "ingest",
        "extract",
        "canonicalize",
        "diff",
        "research",
        "classify",
        "suggest",
        "report",
    ]
    assert all(text.startswith("Phase ") for _, text in seen)


# --- Outils ADK -----------------------------------------------------------


def test_tools_are_declared_with_descriptions():
    """L'ADK construit la déclaration passée au modèle depuis la docstring :
    un outil sans description est un outil inutilisable."""
    assert len(CLEARANCE_TOOLS) == 3
    for tool in CLEARANCE_TOOLS:
        assert tool.name
        assert len(tool.description) > 40


def test_the_rule_tool_settles_a_fictional_phone_number():
    result = check_clearance_rule("555-0147", "PHONE", "neutral")
    assert result["settled"] is True
    assert result["verdict"] == Verdict.CLEAR.value


def test_the_rule_tool_defers_a_business_to_search():
    assert check_clearance_rule("The Black Cat Tavern", "BUSINESS", "illegal") == {"settled": False}


@pytest.mark.parametrize(
    ("entity_type", "tier", "expected"),
    [
        ("BUSINESS", "neutral", "fast"),
        ("BUSINESS", "illegal", "advanced"),
        ("SONG", "neutral", "advanced"),
    ],
)
def test_the_budget_tool_reports_the_depth_without_searching(entity_type, tier, expected):
    assert estimate_search_depth(entity_type, tier)["mode"] == expected

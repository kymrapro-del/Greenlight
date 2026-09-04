"""Le pipeline de clearance, en agents ADK.

**Pourquoi des workflow agents et non un `LlmAgent`.** L'ADK propose les deux.
Un `LlmAgent` laisse le modèle décider quel outil appeler et dans quel ordre —
c'est le bon choix quand le plan dépend de la conversation. Ici il serait
strictement moins bon : l'ordre des huit phases est connu, il ne dépend
d'aucune entrée, et un rapport de clearance doit être reproductible à
l'identique d'un run à l'autre. Le règlement du hackathon demande d'ailleurs un
agent déterministe.

On utilise donc `Workflow` et des `BaseAgent` métier, qui sont la réponse de
l'ADK pour un enchaînement déterministe. Le modèle reste appelé là où il apporte
du jugement — extraction, classification, suggestion — mais il ne pilote pas
l'orchestration.

`Workflow` plutôt que `SequentialAgent` : depuis l'ADK 2.8 le second est
déprécié au profit du premier, qui décrit le pipeline comme un graphe. La chaîne
reste linéaire ici, mais c'est le graphe qui permettra plus tard de paralléliser
la recherche et la classification sans réécrire l'orchestration.

**Ce paquet ne réimplémente rien.** Chaque agent délègue à la fonction qui
existe déjà dans `greenlight.agents`. Un seul endroit définit le comportement,
et la bibliothèque reste utilisable sans l'ADK.

L'état circule par `ctx.session.state`, la mémoire partagée de l'ADK : chaque
phase y lit ce que la précédente a écrit.

**Une contrainte de l'ADK a façonné la découpe.** L'état de session est copié en
profondeur à chaque tour, parce qu'Agent Engine le persiste : il ne peut donc
contenir que des données sérialisables. Les collaborateurs vivants — client
Gemini, client Parallel, cache — sont portés par les agents eux-mêmes, dans
`ClearanceDeps`, et non par l'état. C'est aussi la bonne conception hors ADK :
l'état décrit ce qu'on sait du scénario, les agents savent avec quoi travailler.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any, ClassVar

from google.adk import Workflow
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from greenlight.agents.classify import classify, sort_findings
from greenlight.agents.dedupe import canonicalize
from greenlight.agents.diff import plan
from greenlight.agents.extract import extract_draft
from greenlight.agents.gemini import GeminiClient
from greenlight.agents.replace import suggest_replacements
from greenlight.agents.research import research
from greenlight.ingest.fountain import parse_file
from greenlight.tools.entity_cache import EntityCache
from greenlight.tools.parallel_search import ParallelSearch


@dataclass
class ClearanceDeps:
    """Ce avec quoi les agents travaillent, hors état de session.

    Injectable : c'est ce qui permet de rejouer un run entier hors ligne, et de
    tester le pipeline ADK sans réseau ni clé.
    """

    gemini: GeminiClient = field(default_factory=GeminiClient)
    search: ParallelSearch = field(default_factory=ParallelSearch)
    cache: EntityCache | None = None


# Clés de l'état partagé. Nommées une fois pour que deux agents ne divergent
# jamais sur l'orthographe d'une clé.
SCRIPT_PATH = "script_path"
DRAFT_ID = "draft_id"
DRAFT = "draft"
SCENES = "scene_entities"
ENTITIES = "entities"
RESEARCH = "research"
FINDINGS = "findings"
DIFF = "diff"
PREVIOUS = "previous_run"
SUGGEST = "suggest"


class _PhaseAgent(BaseAgent):
    """Socle commun : exécuter une phase, publier un compte rendu lisible.

    L'événement émis n'est pas cosmétique — c'est la trace que la console ADK,
    Agent Engine et les tests lisent pour suivre l'avancement d'un run.
    """

    # L'état partagé contient des objets métier (Draft, Finding…) que pydantic
    # n'a pas à valider : ce sont les nôtres.
    model_config: ClassVar[dict[str, Any]] = {"arbitrary_types_allowed": True}

    deps: ClearanceDeps

    def _execute(self, state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Rend (compte rendu, modifications d'état). Ne mute jamais `state`."""
        raise NotImplementedError  # pragma: no cover - abstrait

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        summary, delta = self._execute(ctx.session.state)
        # Les changements d'état passent par `state_delta`, pas par une mutation
        # directe. C'est le mécanisme de l'ADK : le runtime les applique avant la
        # phase suivante et le service de session les persiste, ce qui rend un run
        # reprenable et lisible dans la trace d'événements.
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(role="model", parts=[types.Part(text=summary)]),
            actions=EventActions(state_delta=delta),
        )


class IngestAgent(_PhaseAgent):
    """Phase 1 — le fichier de scénario devient des scènes structurées."""

    def _execute(self, state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        draft = parse_file(state[SCRIPT_PATH], draft_id=state.get(DRAFT_ID, "draft-1"))
        summary = (
            f"Phase 1 — {len(draft.scenes)} scènes lues dans « {draft.title or 'sans titre'} »."
        )
        return summary, {DRAFT: draft}


class ExtractionAgent(_PhaseAgent):
    """Phase 2 — une scène, un appel, deux signaux : l'entité et sa dépiction."""

    def _execute(self, state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        scenes = extract_draft(state[DRAFT], self.deps.gemini)
        dropped = sum(len(s.dropped) for s in scenes)
        failed = [s.scene.number for s in scenes if s.error]
        note = f", {len(failed)} scènes en échec {failed}" if failed else ""
        summary = (
            f"Phase 2 — {sum(len(s.entities) for s in scenes)} entités extraites, "
            f"{dropped} écartées par le garde-fou anti-hallucination{note}."
        )
        return summary, {SCENES: scenes}


class CanonicalizeAgent(_PhaseAgent):
    """Phase 3 — déduplication à l'échelle du scénario. Aucun appel modèle."""

    def _execute(self, state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        entities = canonicalize(state[SCENES])
        summary = f"Phase 3 — {len(entities)} entités canoniques après fusion des variantes."
        return summary, {ENTITIES: entities}


class DiffAgent(_PhaseAgent):
    """Phase 8 — placée ici parce qu'elle décide ce que les phases 4 et 5 traitent.

    Sans version précédente, elle ne fait rien et tout le scénario est analysé.
    """

    def _execute(self, state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        previous = state.get(PREVIOUS)
        if previous is None:
            return "Phase 8 — aucune version précédente : analyse complète.", {}

        draft_diff = plan(
            previous.extraction.entities,
            previous.findings,
            state[ENTITIES],
            state.get(DRAFT_ID, "draft-1"),
        )
        # Seules les entités que la réécriture a touchées passent aux phases
        # suivantes ; les verdicts repris sont réintégrés par la phase 7.
        return f"Phase 8 — {draft_diff.summary()}", {
            DIFF: draft_diff,
            ENTITIES: draft_diff.to_analyze,
        }


class ResearchAgent(_PhaseAgent):
    """Phase 4 — fan-out Parallel, entités tranchées par règle exclues."""

    def _execute(self, state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        run = research(state[ENTITIES], self.deps.search, cache=self.deps.cache)
        summary = (
            f"Phase 4 — {len(run.billed)} recherches facturées, "
            f"{len(run.skipped_by_rule)} entités tranchées par règle, "
            f"{len(run.served_from_cache)} servies par le cache."
        )
        return summary, {RESEARCH: run}


class ClassificationAgent(_PhaseAgent):
    """Phase 5 — verdicts ancrés dans les sources, puis règle de dépiction."""

    def _execute(self, state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        findings = classify(
            state[RESEARCH].results, self.deps.gemini, draft_id=state.get(DRAFT_ID, "draft-1")
        )
        escalated = sum(1 for f in findings if f.escalated_from is not None)
        summary = (
            f"Phase 5 — {len(findings)} verdicts rendus, "
            f"{escalated} remontés par la règle de dépiction."
        )
        return summary, {FINDINGS: findings}


class SuggestionAgent(_PhaseAgent):
    """Phase 6 — un remplacement n'est proposé qu'après avoir été re-cherché."""

    def _execute(self, state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        if not state.get(SUGGEST):
            return "Phase 6 — suggestions désactivées pour ce run.", {}

        findings = suggest_replacements(
            state[FINDINGS], state[ENTITIES], self.deps.gemini, self.deps.search
        )
        verified = sum(1 for f in findings if f.replacement_verified)
        summary = f"Phase 6 — {verified} remplacements proposés et re-vérifiés."
        return summary, {FINDINGS: findings}


class ReportAgent(_PhaseAgent):
    """Phase 7 — tri du rapport, et réintégration des verdicts repris."""

    def _execute(self, state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        draft_diff = state.get(DIFF)
        reused = draft_diff.reused if draft_diff else []
        findings = sort_findings(state[FINDINGS] + reused)

        flagged = sum(1 for f in findings if f.verdict.value != "CLEAR")
        summary = (
            f"Phase 7 — rapport de {len(findings)} verdicts, {flagged} à traiter avant le tournage."
        )
        return summary, {FINDINGS: findings}


def build_phases(deps: ClearanceDeps) -> list[_PhaseAgent]:
    """Les huit phases, dans leur ordre d'exécution.

    L'ordre n'est pas celui des numéros de phase : le diff passe avant la
    recherche, parce que c'est lui qui décide ce qu'il reste à chercher. C'est
    tout l'intérêt du mode réécriture.
    """
    return [
        IngestAgent(name="ingest", deps=deps),
        ExtractionAgent(name="extract", deps=deps),
        CanonicalizeAgent(name="canonicalize", deps=deps),
        DiffAgent(name="diff", deps=deps),
        ResearchAgent(name="research", deps=deps),
        ClassificationAgent(name="classify", deps=deps),
        SuggestionAgent(name="suggest", deps=deps),
        ReportAgent(name="report", deps=deps),
    ]


def build_clearance_agent(
    deps: ClearanceDeps | None = None, name: str = "greenlight_clearance"
) -> Workflow:
    """Le pipeline complet, en un agent ADK déployable."""
    phases = build_phases(deps or ClearanceDeps())
    return Workflow(
        name=name,
        description=(
            "Analyse un scénario et rend un rapport de pré-clearance : entités "
            "nommées, verdicts sourcés, remplacements re-vérifiés."
        ),
        # Une arête par transition, plus l'amorce depuis START.
        edges=[("START", phases[0]), *pairwise(phases)],
    )

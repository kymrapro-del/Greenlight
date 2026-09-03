"""Orchestration du pipeline, et point d'entrée en ligne de commande.

    python -m greenlight.pipeline samples/seventeen_minutes.fountain
    python -m greenlight.pipeline samples/seventeen_minutes.fountain --clearance

Sans option, seules les phases 1 → 3 tournent : ingestion, extraction,
canonicalisation. Aucun crédit Parallel n'est touché, ce qui en fait le mode de
travail par défaut pendant le développement.

Avec `--clearance`, les phases 4 et 5 s'ajoutent : fan-out de recherche puis
verdicts sourcés. En `FIXTURE_MODE=replay` cette passe complète ne coûte rien
non plus — c'est ce qui permet d'itérer sur le rapport sans brûler le budget.

Le compte-rendu affiché est volontairement le même que celui qui alimentera la
démo : ce sont ces chiffres-là qu'on annonce, et ils sont mesurés.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from greenlight.agents.classify import classify, sort_findings
from greenlight.agents.dedupe import canonicalize
from greenlight.agents.extract import SceneEntities, extract_draft
from greenlight.agents.gemini import GeminiClient
from greenlight.agents.research import ResearchRun, research
from greenlight.ingest.fountain import parse_file
from greenlight.models import Draft, Entity, Finding, Verdict
from greenlight.tools.parallel_search import ParallelSearch
from greenlight.tools.queries import build_search, choose_mode, pre_verdict


@dataclass
class ExtractionRun:
    draft: Draft
    entities: list[Entity]
    scenes: list[SceneEntities] = field(default_factory=list)
    elapsed_s: float = 0.0
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def dropped_count(self) -> int:
        return sum(len(s.dropped) for s in self.scenes)

    @property
    def failed_scenes(self) -> list[SceneEntities]:
        return [s for s in self.scenes if s.error]

    def resolved_without_search(self) -> list[Entity]:
        """Entités tranchées par règle : autant de recherches non facturées."""
        return [e for e in self.entities if pre_verdict(e) is not None]


def run_extraction(
    path: str | Path, client: GeminiClient | None = None, draft_id: str = "draft-1"
) -> ExtractionRun:
    """Phases 1 → 3 : fichier de scénario → entités canoniques."""
    started = time.monotonic()
    client = client or GeminiClient()

    draft = parse_file(path, draft_id=draft_id)
    scenes = extract_draft(draft, client)
    entities = canonicalize(scenes)

    return ExtractionRun(
        draft=draft,
        entities=entities,
        scenes=scenes,
        elapsed_s=round(time.monotonic() - started, 2),
        usage=client.usage_summary(),
    )


@dataclass
class ClearanceRun:
    """Passe complète : phases 1 → 5, du fichier de scénario aux verdicts."""

    extraction: ExtractionRun
    research: ResearchRun
    findings: list[Finding]
    elapsed_s: float = 0.0
    search_usage: dict[str, float | int] = field(default_factory=dict)
    gemini_usage: dict[str, Any] = field(default_factory=dict)

    def by_verdict(self, verdict: Verdict) -> list[Finding]:
        return [f for f in self.findings if f.verdict is verdict]

    @property
    def flagged(self) -> list[Finding]:
        """Ce que le scénariste doit traiter avant le tournage."""
        return [f for f in self.findings if f.verdict is not Verdict.CLEAR]

    @property
    def escalated(self) -> list[Finding]:
        """Verdicts remontés par la règle de dépiction. La démonstration que les
        deux signaux sont combinés, et pas seulement l'existence."""
        return [f for f in self.findings if f.escalated_from is not None]


def run_clearance(
    path: str | Path,
    client: GeminiClient | None = None,
    search: ParallelSearch | None = None,
    draft_id: str = "draft-1",
    max_workers: int = 8,
) -> ClearanceRun:
    """Phases 1 → 5 : fichier de scénario → verdicts sourcés."""
    started = time.monotonic()
    client = client or GeminiClient()

    extraction = run_extraction(path, client, draft_id=draft_id)
    research_run = research(extraction.entities, search, max_workers=max_workers)
    findings = sort_findings(classify(research_run.results, client, draft_id=draft_id))

    return ClearanceRun(
        extraction=extraction,
        research=research_run,
        findings=findings,
        elapsed_s=round(time.monotonic() - started, 2),
        search_usage=research_run.usage,
        gemini_usage=client.usage_summary(),
    )


def report(run: ExtractionRun) -> str:
    """Compte-rendu console. Les chiffres annoncés dans la démo sortent d'ici."""
    free = run.resolved_without_search()
    free_ids = {e.id for e in free}
    billable = [e for e in run.entities if e.id not in free_ids]
    advanced = [e for e in billable if choose_mode(e) == "advanced"]

    lines = [
        f"Scénario     : {run.draft.title or run.draft.source_path}",
        f"Scènes       : {len(run.draft.scenes)}",
        f"Entités      : {len(run.entities)} canoniques",
        f"Sans recherche : {len(free)} tranchées par règle (0 requête facturée)",
        f"À rechercher : {len(billable)} dont {len(advanced)} en mode advanced",
        f"Écartées     : {run.dropped_count} absentes du texte (garde-fou)",
        f"Durée        : {run.elapsed_s} s",
        f"Gemini (ph.2): {run.usage}",
    ]
    if run.failed_scenes:
        lines.append(f"Scènes en échec : {[s.scene.number for s in run.failed_scenes]}")

    lines.append("")
    lines.append("Entités :")
    for entity in run.entities:
        verdict = pre_verdict(entity)
        tag = verdict.verdict.value if verdict else choose_mode(entity)
        scenes_seen = sorted({o.scene_number for o in entity.occurrences})
        lines.append(
            f"  [{tag:<18}] {entity.canonical_name}  "
            f"({entity.type.value}, {entity.worst_context.value}, scènes {scenes_seen})"
        )
    return "\n".join(lines)


def clearance_report(run: ClearanceRun) -> str:
    """Le rapport tel qu'il sera lu. Chiffres mesurés, verdicts sourcés."""
    findings = run.findings
    lines = [
        report(run.extraction),
        "",
        "─" * 72,
        f"Verdicts     : {len(findings)} — {len(run.flagged)} à traiter avant tournage",
    ]
    for verdict in Verdict:
        count = len(run.by_verdict(verdict))
        if count:
            lines.append(f"  {verdict.value:<20} {count}")

    lines += [
        f"Recherche    : {run.search_usage}",
        f"Gemini (tout): {run.gemini_usage}",
        f"Durée totale : {run.elapsed_s} s",
    ]
    if run.research.failed:
        lines.append(
            f"Recherches en échec : {[r.entity.canonical_name for r in run.research.failed]}"
        )

    lines.append("")
    for finding in findings:
        entity = next(e for e in run.extraction.entities if e.id == finding.entity_id)
        lines.append(f"[{finding.verdict.value}] {entity.canonical_name}")
        lines.append(f"    {finding.rationale}")
        if finding.escalated_from is not None:
            lines.append(
                f"    ↑ remonté depuis {finding.escalated_from.value} — dépiction "
                f"« {finding.context_tier.value} » dans le scénario"
            )
        for citation in finding.citations[:3]:
            lines.append(f"    · {citation.title or citation.url}")
            lines.append(f"      {citation.url}")
        if not finding.citations and finding.search_mode:
            lines.append("    · aucune source retenue")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GREENLIGHT — pipeline de clearance")
    parser.add_argument("script", help="chemin d'un fichier .fountain")
    parser.add_argument(
        "--clearance",
        action="store_true",
        help="ajoute les phases 4 et 5 : recherche Parallel puis verdicts sourcés",
    )
    parser.add_argument(
        "--queries",
        action="store_true",
        help="affiche les requêtes Parallel qui seraient émises (sans les émettre)",
    )
    args = parser.parse_args(argv)

    if args.clearance:
        run = run_clearance(args.script)
        print(clearance_report(run))
        extraction = run.extraction
    else:
        extraction = run_extraction(args.script)
        print(report(extraction))

    if args.queries:
        print("\nRequêtes Parallel prévues :")
        for entity in extraction.entities:
            if pre_verdict(entity) is not None:
                continue
            spec = build_search(entity, scene_hint=entity.occurrences[0].quote[:80])
            print(f"  {entity.canonical_name} [{spec.mode}]")
            for query in spec.queries:
                print(f"      {query}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

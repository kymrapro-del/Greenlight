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
from greenlight.agents.diff import DraftDiff, plan
from greenlight.agents.extract import SceneEntities, extract_draft
from greenlight.agents.gemini import GeminiClient
from greenlight.agents.replace import suggest_replacements
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
    # Renseigné quand la passe s'appuie sur une version précédente.
    diff: DraftDiff | None = None

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

    @property
    def verified_replacements(self) -> list[Finding]:
        """Remplacements proposés ET repassés par la recherche sans résultat."""
        return [f for f in self.findings if f.replacement_verified]


def run_clearance(
    path: str | Path,
    client: GeminiClient | None = None,
    search: ParallelSearch | None = None,
    draft_id: str = "draft-1",
    max_workers: int = 8,
    suggest: bool = False,
    previous: ClearanceRun | None = None,
) -> ClearanceRun:
    """Passe de clearance sur un scénario.

    Avec `previous`, seules les entités que la réécriture a réellement touchées
    repartent dans le pipeline ; les autres gardent leur verdict. Avec
    `suggest`, les entités à corriger reçoivent un remplacement re-vérifié.
    """
    started = time.monotonic()
    client = client or GeminiClient()
    search = search or ParallelSearch()

    extraction = run_extraction(path, client, draft_id=draft_id)

    if previous is not None:
        draft_diff = plan(
            previous.extraction.entities, previous.findings, extraction.entities, draft_id
        )
        targets, reused = draft_diff.to_analyze, draft_diff.reused
    else:
        draft_diff, targets, reused = None, extraction.entities, []

    research_run = research(targets, search, max_workers=max_workers)
    findings = classify(research_run.results, client, draft_id=draft_id)

    if suggest:
        findings = suggest_replacements(findings, extraction.entities, client, search)

    return ClearanceRun(
        extraction=extraction,
        research=research_run,
        findings=sort_findings(findings + reused),
        elapsed_s=round(time.monotonic() - started, 2),
        search_usage=search.usage_summary(),
        gemini_usage=client.usage_summary(),
        diff=draft_diff,
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

    if run.diff is not None:
        lines += ["", f"Diff         : {run.diff.summary()}"]
        if run.diff.added:
            lines.append(f"  nouvelles  : {[e.canonical_name for e in run.diff.added]}")
        if run.diff.recontextualized:
            lines.append(f"  redépeintes: {[e.canonical_name for e in run.diff.recontextualized]}")
        if run.diff.removed:
            lines.append(f"  disparues  : {[e.canonical_name for e in run.diff.removed]}")

    lines += [
        "",
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
        if finding.suggested_replacement:
            mark = (
                "re-vérifié, aucun résultat réel"
                if finding.replacement_verified
                else "non vérifié — à relire"
            )
            lines.append(f"    → remplacer par « {finding.suggested_replacement} » ({mark})")
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
        "--suggest",
        action="store_true",
        help="propose un remplacement re-vérifié pour chaque entité à corriger",
    )
    parser.add_argument(
        "--against",
        metavar="SCRIPT_V1",
        help="version précédente : seules les entités réellement touchées sont réanalysées",
    )
    parser.add_argument(
        "--queries",
        action="store_true",
        help="affiche les requêtes Parallel qui seraient émises (sans les émettre)",
    )
    args = parser.parse_args(argv)

    if args.clearance or args.against or args.suggest:
        previous = None
        if args.against:
            previous = run_clearance(args.against, draft_id="draft-1", suggest=args.suggest)
            print(clearance_report(previous))
            print("\n" + "=" * 72 + "\nVERSION SUIVANTE\n" + "=" * 72 + "\n")
        run = run_clearance(
            args.script,
            draft_id="draft-2" if previous else "draft-1",
            suggest=args.suggest,
            previous=previous,
        )
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

"""Orchestration des phases 1 → 3, et point d'entrée en ligne de commande.

    python -m greenlight.pipeline samples/seventeen_minutes.fountain

Ce module chaîne l'ingestion, l'extraction et la canonicalisation, puis rend un
état complet du scénario : entités canoniques, occurrences, contexte de
dépiction, et la consommation réellement mesurée. Les phases 4 et 5 —
recherche Parallel et classification — s'y branchent ensuite sans rien changer
en amont.

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

from greenlight.agents.dedupe import canonicalize
from greenlight.agents.extract import SceneEntities, extract_draft
from greenlight.agents.gemini import GeminiClient
from greenlight.ingest.fountain import parse_file
from greenlight.models import Draft, Entity
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
        f"Gemini       : {run.usage}",
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GREENLIGHT — extraction phases 1 à 3")
    parser.add_argument("script", help="chemin d'un fichier .fountain")
    parser.add_argument(
        "--queries",
        action="store_true",
        help="affiche aussi les requêtes Parallel qui seraient émises (sans les émettre)",
    )
    args = parser.parse_args(argv)

    run = run_extraction(args.script)
    print(report(run))

    if args.queries:
        print("\nRequêtes Parallel prévues :")
        for entity in run.entities:
            if pre_verdict(entity) is not None:
                continue
            spec = build_search(entity, scene_hint=entity.occurrences[0].quote[:80])
            print(f"  {entity.canonical_name} [{spec.mode}]")
            for query in spec.queries:
                print(f"      {query}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Sérialisation d'une passe de clearance vers le rapport affiché.

Un seul endroit décide de la forme envoyée à l'interface. Les noms sont en
camelCase parce que c'est la convention du consommateur : la frontière entre les
deux mondes se traverse ici, une fois, plutôt que dans chaque composant.

Le champ `placeholder` n'est pas décoratif. Tant que le rapport n'a pas été
produit par un vrai passage sur les API, il vaut `true` et l'interface le dit à
l'écran. Montrer des verdicts fabriqués sans le signaler serait exactement le
genre de raccourci qui se paie devant un jury.
"""

from __future__ import annotations

from typing import Any

from greenlight.models import Entity, Finding
from greenlight.pipeline import ClearanceRun
from greenlight.tools.queries import pre_verdict


def _occurrence_payload(entity: Entity) -> list[dict[str, Any]]:
    return [
        {
            "sceneId": o.scene_id,
            "sceneNumber": o.scene_number,
            "contextTier": o.context_tier.value,
            "quote": o.quote,
        }
        for o in entity.occurrences
    ]


def finding_payload(finding: Finding, entity: Entity, reused: bool = False) -> dict[str, Any]:
    return {
        # Vrai quand le verdict vient de la version précédente sans avoir été
        # recalculé. L'interface le montre : c'est ce qui rend visible ce que le
        # diff a réellement économisé, entité par entité.
        "reusedFromPreviousDraft": reused,
        "id": finding.id,
        "entityId": finding.entity_id,
        "name": entity.canonical_name,
        "type": entity.type.value,
        "aliases": entity.aliases,
        "verdict": finding.verdict.value,
        "confidence": round(finding.confidence, 2),
        "rationale": finding.rationale,
        "contextTier": finding.context_tier.value,
        # Renseigné quand la règle de dépiction a fait monter le verdict. C'est
        # la trace visible du raisonnement, affichée telle quelle dans le détail.
        "escalatedFrom": finding.escalated_from.value if finding.escalated_from else None,
        "searchMode": finding.search_mode,
        "resolvedByRule": finding.search_mode is None and pre_verdict(entity) is not None,
        "suggestedReplacement": finding.suggested_replacement,
        "replacementVerified": finding.replacement_verified,
        "scenes": sorted({o.scene_number for o in entity.occurrences}),
        "occurrences": _occurrence_payload(entity),
        "citations": [
            {
                "url": c.url,
                "title": c.title,
                "excerpt": c.excerpt,
                "publishDate": c.publish_date,
            }
            for c in finding.citations
        ],
    }


def to_payload(run: ClearanceRun, placeholder: bool = False) -> dict[str, Any]:
    """Le rapport complet, tel que l'interface le consomme."""
    entities = {e.id: e for e in run.extraction.entities}
    reused_ids = {f.entity_id for f in run.diff.reused} if run.diff else set()
    findings = [
        finding_payload(f, entities[f.entity_id], reused=f.entity_id in reused_ids)
        for f in run.findings
        if f.entity_id in entities
    ]

    payload: dict[str, Any] = {
        "placeholder": placeholder,
        "title": run.extraction.draft.title or "Sans titre",
        "draftId": run.extraction.draft.id,
        "sceneCount": len(run.extraction.draft.scenes),
        "stats": {
            "entities": len(run.extraction.entities),
            "flagged": len(run.flagged),
            "resolvedByRule": len(run.research.skipped_by_rule),
            "servedFromCache": len(run.research.served_from_cache),
            "billedSearches": len(run.research.billed),
            "droppedHallucinations": run.extraction.dropped_count,
            "escalated": len(run.escalated),
            "elapsedS": run.elapsed_s,
        },
        "usage": {"search": run.search_usage, "gemini": run.gemini_usage},
        "findings": findings,
    }

    # Une scène perdue ne disparaît pas en silence. Sans ça, un scénario dont
    # toutes les scènes échouent rend « 0 entité » — exactement la même chose
    # qu'un scénario propre, et le lecteur conclut à tort qu'il n'y a rien à
    # signaler. Le diagnostic prime sur le chiffre.
    failed = run.extraction.failed_scenes
    if failed:
        payload["failedScenes"] = [
            {"number": scene.scene.number, "heading": scene.scene.heading, "error": scene.error}
            for scene in failed
        ]
        payload["degraded"] = len(failed) == len(run.extraction.draft.scenes)

    if run.diff is not None:
        payload["diff"] = {
            "summary": run.diff.summary(),
            "reanalyzed": len(run.diff.to_analyze),
            "reused": run.diff.unchanged_count,
            "added": [e.canonical_name for e in run.diff.added],
            "recontextualized": [e.canonical_name for e in run.diff.recontextualized],
            "removed": [e.canonical_name for e in run.diff.removed],
        }

    return payload

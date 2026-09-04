"""Conversation ancrée — répondre à une question sur un rapport déjà produit.

C'est ce qui fait la différence entre un rapport affiché et un assistant : le
scénariste lit « À changer » sur le nom de son bar et demande *pourquoi*, ou
*qu'est-ce que je mets à la place*, ou *et si la scène était neutre*. Sans cette
phase, l'interface est une page de résultats déguisée en chat.

Trois règles, et elles sont contraignantes.

**Le modèle ne voit que le rapport.** Pas le web, pas sa mémoire des faits : le
contexte envoyé est la liste des entités, leurs verdicts, leurs justifications
et leurs sources, telle qu'elle a été produite. Une réponse qui inventerait un
fait juridique sur une entreprise réelle serait exactement le risque que ce
produit prétend réduire.

**Une réponse cite ses entités.** Le champ `entity_ids` renvoie les entités sur
lesquelles la réponse s'appuie, et il est validé contre le rapport : un
identifiant inconnu est écarté. L'interface s'en sert pour ouvrir la bonne ligne.

**Une question hors du rapport reçoit un refus, pas une improvisation.**
`answerable` à faux, et l'interface affiche la limite plutôt qu'une réponse
plausible.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from greenlight.agents.gemini import GeminiClient
from greenlight.config import settings

SYSTEM_INSTRUCTION = """\
You are the clearance analyst who produced the report below, answering a \
follow-up question from the screenwriter who wrote the screenplay.

Answer ONLY from the report you are given. It is your entire knowledge: the \
entities found in the screenplay, the verdict on each, the reasoning, and the \
sources that were actually retrieved.

Hard rules:
- Never state a fact about a real company, person, place or work that is not in \
the report. If the report does not say it, you do not know it.
- Never invent a source, a URL, a lawsuit, or a rights holder.
- If the question cannot be answered from the report, set `answerable` to false \
and say in one sentence what would be needed. Do not guess.
- List in `entity_ids` the ids of the report entries your answer relies on. Use \
only ids present in the report.

Style: you are talking to a writer, not a lawyer. Short paragraphs, plain \
language, no legal jargon, no disclaimers — the interface already carries the \
scoping notice. Answer in the language the question is written in.

You may reason about the report: compare entries, rank what to fix first, \
explain why a depiction escalated a verdict, or propose a rewrite of a line. \
That is analysis of the report, not new knowledge, and it is what is wanted.
"""


class Answer(BaseModel):
    """Ce que le modèle doit rendre. Le schéma est le contrat."""

    answerable: bool = Field(
        description="False when the report does not contain what the question needs."
    )
    answer: str = Field(description="The reply to the writer. Plain language, no jargon.")
    entity_ids: list[str] = Field(
        default_factory=list,
        description="Ids of the report entries the answer relies on.",
    )


def build_context(report: dict[str, Any], max_findings: int = 40) -> str:
    """Le rapport, mis à plat pour le modèle.

    Les entités arrivent déjà triées par sévérité : tronquer garde donc ce qui
    compte. Les extraits de sources sont coupés — le modèle a besoin de savoir
    ce que la source dit, pas de la relire en entier.
    """
    lines = [
        f"SCREENPLAY: {report.get('title', 'Untitled')}",
        f"SCENES: {report.get('sceneCount', 0)}",
        "",
    ]
    stats = report.get("stats") or {}
    if stats:
        lines += [
            f"{stats.get('entities', 0)} entities found, "
            f"{stats.get('flagged', 0)} need action before shooting, "
            f"{stats.get('escalated', 0)} escalated by how the scene depicts them.",
            "",
        ]

    for finding in (report.get("findings") or [])[:max_findings]:
        lines.append(f"--- [{finding['id']}] {finding['name']} ({finding['type']})")
        lines.append(f"VERDICT: {finding['verdict']} (confidence {finding.get('confidence')})")
        if finding.get("escalatedFrom"):
            lines.append(
                f"ESCALATED FROM {finding['escalatedFrom']} because the scene depicts it as "
                f"{finding.get('contextTier')}."
            )
        if finding.get("resolvedByRule"):
            lines.append("RESOLVED BY PROFESSIONAL CONVENTION, with no search performed.")
        lines.append(f"REASONING: {finding.get('rationale', '')}")
        if finding.get("suggestedReplacement"):
            verified = (
                "re-verified against search" if finding.get("replacementVerified") else "unverified"
            )
            lines.append(f"SUGGESTED REPLACEMENT: {finding['suggestedReplacement']} ({verified})")
        for occurrence in finding.get("occurrences", [])[:3]:
            lines.append(
                f"IN SCENE {occurrence['sceneNumber']} ({occurrence['contextTier']}): "
                f"{occurrence['quote']}"
            )
        for citation in finding.get("citations", [])[:3]:
            excerpt = (citation.get("excerpt") or "")[:300]
            lines.append(f"SOURCE: {citation.get('title') or citation['url']} — {excerpt}")
        lines.append("")

    return "\n".join(lines)


def ask(
    question: str,
    report: dict[str, Any],
    client: GeminiClient | None = None,
    model: str | None = None,
    history: list[tuple[str, str]] | None = None,
) -> Answer:
    """Une question, le rapport, une réponse ancrée.

    Les identifiants d'entités rendus par le modèle sont filtrés sur ceux du
    rapport : le lien que l'interface ouvre ne peut donc pas pointer dans le vide.
    """
    client = client or GeminiClient()

    parts = ["REPORT", "======", build_context(report), ""]
    for previous_question, previous_answer in (history or [])[-3:]:
        parts += [f"EARLIER QUESTION: {previous_question}", f"YOUR ANSWER: {previous_answer}", ""]
    parts += ["QUESTION", "========", question.strip()]

    answer = client.structured(
        model=model or settings.model_classify,
        system=SYSTEM_INSTRUCTION,
        prompt="\n".join(parts),
        schema=Answer,
        # Une réponse conversationnelle a le droit de varier un peu dans sa
        # formulation ; le fond, lui, est contraint par le rapport et le schéma.
        temperature=0.2,
    )

    known = {f["id"] for f in report.get("findings") or []}
    answer.entity_ids = [entity_id for entity_id in answer.entity_ids if entity_id in known]
    return answer

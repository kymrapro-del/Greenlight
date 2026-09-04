"""Exécution du pipeline via le runtime ADK.

Le point important est la garantie de sortie : `run_clearance_agent` rend un
`ClearanceRun`, exactement le même objet que `greenlight.pipeline.run_clearance`.
Les deux chemins d'exécution partagent donc leur contrat, l'API et l'écran
Rapport ne savent pas lequel les a produits, et un test peut vérifier qu'ils
concordent.

Le runtime ADK est asynchrone. `run_clearance_agent` est la version bloquante,
pour la ligne de commande et les tests ; `arun_clearance_agent` reste disponible
quand l'appelant a déjà une boucle d'événements — c'est le cas d'Agent Engine.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator, Callable
from pathlib import Path

from google.adk.events import Event
from google.adk.runners import InMemoryRunner
from google.genai import types

from greenlight.adk.agents import (
    DIFF,
    DRAFT,
    DRAFT_ID,
    FINDINGS,
    PREVIOUS,
    RESEARCH,
    SCENES,
    SCRIPT_PATH,
    SUGGEST,
    ClearanceDeps,
    build_clearance_agent,
)
from greenlight.agents.dedupe import canonicalize
from greenlight.agents.gemini import GeminiClient
from greenlight.pipeline import ClearanceRun, ExtractionRun
from greenlight.tools.entity_cache import EntityCache
from greenlight.tools.parallel_search import ParallelSearch

APP_NAME = "greenlight"
USER_ID = "local"


async def arun_clearance_agent(
    path: str | Path,
    draft_id: str = "draft-1",
    suggest: bool = False,
    previous: ClearanceRun | None = None,
    client: GeminiClient | None = None,
    search: ParallelSearch | None = None,
    cache: EntityCache | None = None,
    on_event: Callable[[str, str], None] | None = None,
) -> ClearanceRun:
    """Exécute l'agent ADK et reconstitue le `ClearanceRun`.

    `on_event` reçoit `(nom de l'agent, compte rendu)` à chaque phase terminée.
    C'est ce qui alimente une barre de progression sans que l'appelant ait à
    connaître le runtime ADK.
    """
    started = time.monotonic()

    # Les collaborateurs vivants sont portés par les agents, pas par l'état :
    # l'ADK copie l'état en profondeur, et un client qui détient un verrou n'est
    # pas copiable. C'est aussi ce qui rend le run rejouable hors ligne.
    deps = ClearanceDeps(
        gemini=client or GeminiClient(),
        search=search or ParallelSearch(),
        cache=cache,
    )
    runner = InMemoryRunner(agent=build_clearance_agent(deps), app_name=APP_NAME)

    state = {
        SCRIPT_PATH: str(path),
        DRAFT_ID: draft_id,
        SUGGEST: suggest,
        PREVIOUS: previous,
    }

    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, state=state
    )

    # Le runtime ADK veut un message d'entrée : c'est la demande elle-même.
    # Le chemin y figure pour que la trace d'un run dise sur quoi il a porté.
    events: AsyncGenerator[Event, None] = runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=f"Rapport de pré-clearance pour {path}")],
        ),
    )
    async for event in events:
        if on_event and event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts)
            if text:
                on_event(event.author, text)

    # L'état lu en sortie est celui de la session, que le runtime a fait vivre.
    final = (
        await runner.session_service.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session.id
        )
    ).state
    gemini, parallel = deps.gemini, deps.search

    extraction = ExtractionRun(
        draft=final[DRAFT],
        # L'état ne contient que les entités restant à analyser après le diff ;
        # le rapport, lui, doit connaître tout le scénario.
        entities=canonicalize(final[SCENES]),
        scenes=final[SCENES],
        usage=gemini.usage_summary(),
    )

    return ClearanceRun(
        extraction=extraction,
        research=final[RESEARCH],
        findings=final[FINDINGS],
        elapsed_s=round(time.monotonic() - started, 2),
        search_usage=parallel.usage_summary(),
        gemini_usage=gemini.usage_summary(),
        diff=final.get(DIFF),
    )


def run_clearance_agent(*args, **kwargs) -> ClearanceRun:
    """Version bloquante d'`arun_clearance_agent`."""
    return asyncio.run(arun_clearance_agent(*args, **kwargs))

"""Le serveur HTTP : le pipeline, joignable depuis l'interface.

C'est ce qui sépare une maquette d'un produit. L'écran ne lit plus un rapport
posé sur le disque : il dépose un scénario, le serveur lance les huit phases, et
la progression remonte pendant que ça tourne.

**La progression est diffusée, pas attendue.** Une passe complète prend des
dizaines de secondes ; une requête qui rend tout à la fin donne un écran de
chargement muet, et le plan de démonstration l'interdit explicitement. Chaque
phase émet donc un événement `text/event-stream` dès qu'elle démarre, et le
rapport arrive en dernier événement. Le pipeline, lui, ne connaît ni HTTP ni
SSE : il appelle un `PhaseHook`, et c'est ici seulement que ça devient un flux.

**Un scénario déposé ne touche jamais le disque.** Il est parsé en mémoire, la
passe est gardée dans le store, et rien n'est écrit : le texte d'un scénariste
n'a aucune raison de rester sur un serveur de démonstration.

**Le mode fixtures est annoncé.** `/api/health` dit si l'instance appelle
vraiment Gemini et Parallel ou rejoue des enregistrements, et le rapport porte
`placeholder`. L'interface l'affiche. Une démonstration qui laisserait croire à
des appels réels alors qu'elle rejoue un disque serait un mensonge sur le seul
point qui compte pour un jury.
"""

from __future__ import annotations

import json
import queue
import threading
from collections.abc import Iterator
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from greenlight.agents.ask import ask
from greenlight.agents.gemini import GeminiClient
from greenlight.api.report import to_payload
from greenlight.config import REPO_ROOT, settings
from greenlight.pipeline import as_draft, run_clearance
from greenlight.store.runs import store
from greenlight.tools.parallel_search import ParallelSearch

SAMPLES_DIR = REPO_ROOT / "samples"

# Les scénarios livrés avec le produit. Le jury ne déposera pas le sien : il
# clique, et une vraie passe part sur un texte que le dépôt contient.
SAMPLES = [
    {
        "id": "seventeen-minutes",
        "file": "seventeen_minutes.fountain",
        "title": "Seventeen Minutes",
        "subtitle": "Premier jet — 12 pages, pièges de clearance sur toutes les catégories",
    },
    {
        "id": "seventeen-minutes-v2",
        "file": "seventeen_minutes_v2.fountain",
        "title": "Seventeen Minutes — réécriture",
        "subtitle": "Deux entités renommées, un numéro corrigé, une scène ajoutée",
        "previousOf": "seventeen-minutes",
    },
]

app = FastAPI(
    title="GREENLIGHT",
    description="Pré-clearance de scénario. Repérer le risque juridique tant qu'il est gratuit à corriger.",
    version="0.2.0",
)

# L'interface est servie depuis une autre origine (Vercel) que l'API. Sans
# authentification et sans cookie, `*` est le réglage honnête : restreindre à un
# domaine donnerait l'illusion d'un contrôle d'accès qui n'existe pas.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Contrats
# --------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    text: str | None = Field(default=None, description="Scénario au format Fountain.")
    sample_id: str | None = Field(default=None, alias="sampleId")
    # Passe précédente : seules les entités réellement touchées repartent dans
    # le pipeline. C'est la phase 8, exposée telle quelle.
    previous_run_id: str | None = Field(default=None, alias="previousRunId")
    suggest: bool = True

    model_config = {"populate_by_name": True}


class AskRequest(BaseModel):
    run_id: str = Field(alias="runId")
    question: str

    model_config = {"populate_by_name": True}


# --------------------------------------------------------------------------
# État de l'instance
# --------------------------------------------------------------------------


def build_clients() -> tuple[GeminiClient, ParallelSearch]:
    """Les deux transports d'une passe, construits en un seul endroit.

    C'est la couture par laquelle les tests remplacent le réseau : la suite
    substitue cette fonction et exerce alors le vrai serveur, le vrai pipeline et
    la vraie sérialisation, sans un appel sortant. Un test qui n'exercerait que
    des composants isolés ne dirait rien de l'API.
    """
    return GeminiClient(), ParallelSearch()


def _live_mode() -> bool:
    """Vrai quand cette instance appelle réellement les API."""
    return settings.fixture_mode in {"live", "record"}


@app.get("/api/health")
def health() -> dict[str, Any]:
    credentials = bool(settings.parallel_api_key) and bool(
        settings.google_api_key or (settings.use_vertex and settings.project)
    )
    return {
        "status": "ok",
        "live": _live_mode() and credentials,
        "fixtureMode": settings.fixture_mode,
        "credentials": credentials,
        "models": {"extract": settings.model_extract, "classify": settings.model_classify},
        "runsHeld": len(store),
    }


@app.get("/api/samples")
def samples() -> list[dict[str, Any]]:
    out = []
    for sample in SAMPLES:
        path = SAMPLES_DIR / sample["file"]
        if not path.exists():
            continue
        draft = as_draft(path, draft_id=sample["id"])
        out.append(
            {
                "id": sample["id"],
                "title": sample["title"],
                "subtitle": sample["subtitle"],
                "scenes": len(draft.scenes),
                # La dernière scène commence à la page N : le scénario en fait
                # au moins N. C'est une estimation, et elle est présentée comme
                # telle plutôt qu'affichée à la décimale.
                "pages": int(draft.scenes[-1].page_start or 1) if draft.scenes else 0,
                "previousOf": sample.get("previousOf"),
            }
        )
    return out


def _sample_text(sample_id: str) -> str:
    for sample in SAMPLES:
        if sample["id"] == sample_id:
            path = SAMPLES_DIR / sample["file"]
            if path.exists():
                return path.read_text(encoding="utf-8")
    raise HTTPException(status_code=404, detail=f"Scénario inconnu : {sample_id}")


# --------------------------------------------------------------------------
# Phase 1 → 8, diffusées
# --------------------------------------------------------------------------

# Ce que l'interface annonce pendant qu'une phase tourne. Les libellés sont ici
# et pas dans le client : c'est le serveur qui sait ce qu'il fait.
_SENTINEL = object()


def _event(name: str, payload: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _analysis_events(request: AnalyzeRequest) -> Iterator[str]:
    """Lance la passe dans un thread et rend les événements au fil de l'eau.

    Le pipeline est synchrone et parallélise déjà ses propres appels. Le faire
    tourner à côté et lire une file est plus simple, et surtout plus honnête,
    que de le réécrire en asynchrone pour le seul besoin de l'affichage.
    """
    text = request.text
    if request.sample_id and not text:
        text = _sample_text(request.sample_id)
    if not text or not text.strip():
        yield _event("error", {"message": "Aucun scénario fourni."})
        return

    previous = None
    if request.previous_run_id:
        stored = store.get(request.previous_run_id)
        if stored is None:
            yield _event(
                "error",
                {"message": f"Passe précédente introuvable : {request.previous_run_id}"},
            )
            return
        previous = stored.run

    events: queue.Queue[Any] = queue.Queue()
    result: dict[str, Any] = {}

    def on_phase(phase: str, message: str, **data: Any) -> None:
        events.put(("phase", {"phase": phase, "message": message, **data}))

    client, search = build_clients()

    def work() -> None:
        try:
            run = run_clearance(
                text,
                client=client,
                search=search,
                draft_id=request.sample_id or "draft",
                suggest=request.suggest,
                previous=previous,
                on_phase=on_phase,
            )
            payload = to_payload(run, placeholder=not _live_mode())
            if payload.get("degraded"):
                # Toutes les scènes ont échoué : il n'y a pas de rapport, il y a
                # une panne. La rendre comme un rapport vide serait affirmer
                # qu'un scénario truffé de pièges n'en contient aucun.
                first = payload["failedScenes"][0]["error"]
                raise RuntimeError(
                    f"Aucune scène n'a pu être analysée ({len(payload['failedScenes'])} sur "
                    f"{payload['sceneCount']}). Première cause : {first}"
                )
            stored = store.add(payload, run, text)
            result["payload"] = stored.payload
        except Exception as exc:  # remonté tel quel : une panne muette est pire
            result["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            events.put(_SENTINEL)

    worker = threading.Thread(target=work, daemon=True)
    worker.start()

    yield _event("started", {"scenes": len(as_draft(text).scenes)})

    while True:
        item = events.get()
        if item is _SENTINEL:
            break
        name, payload = item
        yield _event(name, payload)

    worker.join()

    if "error" in result:
        yield _event("error", {"message": result["error"]})
    else:
        yield _event("report", result["payload"])


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest) -> StreamingResponse:
    return StreamingResponse(
        _analysis_events(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Sans ça, un proxy tamponne le flux et la progression arrive d'un
            # bloc à la fin — soit exactement ce que le flux devait éviter.
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    stored = store.get(run_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Passe inconnue ou expirée.")
    return stored.payload


@app.post("/api/ask")
def ask_about_run(request: AskRequest) -> dict[str, Any]:
    stored = store.get(request.run_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Passe inconnue ou expirée.")

    client, _ = build_clients()
    try:
        answer = ask(request.question, stored.payload, client=client, history=stored.history)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"{type(exc).__name__}: {exc}") from exc

    if answer.answerable:
        store.remember(request.run_id, request.question, answer.answer)

    return {
        "answerable": answer.answerable,
        "answer": answer.answer,
        "entityIds": answer.entity_ids,
    }

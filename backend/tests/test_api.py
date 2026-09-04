"""L'API HTTP, de bout en bout.

Le réseau est remplacé, rien d'autre. Ces tests montent le vrai serveur, qui
lance le vrai pipeline sur le vrai scénario de démonstration et sérialise le
vrai rapport : c'est la jonction entre le produit et son interface, et c'est
exactement l'endroit où une régression casse la démo sans casser un seul test
unitaire.

Le flux SSE est lu comme le navigateur le lira — événement par événement — parce
que la promesse tenue à l'écran est la progression, pas seulement le résultat.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from greenlight.agents.gemini import GeminiClient
from greenlight.api import server
from greenlight.store.runs import RunStore
from tests.test_pipeline import ScriptedSearch, _dual_transport


def _transport(request: dict[str, Any]) -> dict[str, Any]:
    """Le transport des tests de pipeline, plus la phase de conversation."""
    if request["schema"] == "Answer":
        # Le premier identifiant que le contexte contient réellement, plus un
        # inventé : la réponse doit garder le premier et perdre le second.
        real = re.findall(r"--- \[([^\]]+)\]", request["prompt"])
        body = {
            "answerable": True,
            "answer": "Le bar est réel et la scène y place un délit.",
            "entity_ids": [*real[:1], "inexistant"],
        }
        return {"json": json.dumps(body), "usage": {"prompt_tokens": 400, "output_tokens": 60}}
    if request["schema"] == "ReplacementCandidates":
        return {
            "json": json.dumps({"candidates": ["The Amber Room"]}),
            "usage": {"prompt_tokens": 200, "output_tokens": 20},
        }
    return _dual_transport(request)


@pytest.fixture
def client(monkeypatch) -> TestClient:
    """Un serveur dont les deux transports sont scriptés, et un store vierge."""

    def build_clients():
        gemini = GeminiClient(transport=_transport)
        gemini._fixtures.mode = "live"  # le faux transport remplace le réseau
        return gemini, ScriptedSearch()

    monkeypatch.setattr(server, "build_clients", build_clients)
    monkeypatch.setattr(server, "store", RunStore())
    monkeypatch.setattr("greenlight.store.runs.store", server.store)
    return TestClient(server.app)


def _stream(client: TestClient, body: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Lit le flux SSE comme le fera le navigateur : par événements nommés."""
    events: list[tuple[str, dict[str, Any]]] = []
    with client.stream("POST", "/api/analyze", json=body) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        name = None
        for line in response.iter_lines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: ") and name:
                events.append((name, json.loads(line[6:])))
    return events


# --------------------------------------------------------------------------


def test_health_says_whether_the_instance_actually_calls_the_apis(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    # La suite tourne en replay : l'instance ne doit surtout pas se déclarer live.
    assert body["live"] is False
    assert body["fixtureMode"] == "replay"


def test_samples_are_served_with_their_real_scene_count(client):
    samples = client.get("/api/samples").json()
    ids = [s["id"] for s in samples]
    assert ids == ["seventeen-minutes", "seventeen-minutes-v2"]
    assert samples[0]["scenes"] == 6
    # La réécriture ajoute une scène : le chiffre servi vient du parser, pas
    # d'une constante.
    assert samples[1]["scenes"] == 7
    assert samples[1]["previousOf"] == "seventeen-minutes"


def test_analysis_streams_its_phases_then_the_report(client):
    events = _stream(client, {"sampleId": "seventeen-minutes"})
    names = [name for name, _ in events]

    assert names[0] == "started"
    assert names[-1] == "report", f"le flux ne se termine pas par le rapport : {names}"
    # Les phases annoncées sont celles que le pipeline traverse réellement.
    for phase in ("ingest", "extract", "canonicalize", "research", "classify"):
        assert any(payload.get("phase") == phase for name, payload in events if name == "phase"), (
            f"phase absente du flux : {phase}"
        )

    report = events[-1][1]
    assert report["stats"]["entities"] == 15
    assert report["placeholder"] is True  # replay : l'écran doit le dire
    assert report["runId"]


def test_the_report_served_is_the_report_stored(client):
    report = _stream(client, {"sampleId": "seventeen-minutes"})[-1][1]
    again = client.get(f"/api/runs/{report['runId']}").json()
    assert again == report


def test_an_unknown_run_is_a_404_not_an_empty_report(client):
    assert client.get("/api/runs/nexistepas").status_code == 404


def test_a_rewrite_reuses_the_verdicts_the_diff_did_not_touch(client):
    first = _stream(client, {"sampleId": "seventeen-minutes"})[-1][1]
    second = _stream(client, {"sampleId": "seventeen-minutes-v2", "previousRunId": first["runId"]})[
        -1
    ][1]

    assert second["diff"]["reanalyzed"] < second["stats"]["entities"]
    assert second["diff"]["reused"] > 0
    # Le diff est annoncé pendant la passe, pas seulement dans le rapport final.
    events = _stream(client, {"sampleId": "seventeen-minutes-v2", "previousRunId": first["runId"]})
    assert any(payload.get("phase") == "diff" for name, payload in events if name == "phase")


def test_an_empty_screenplay_is_refused_rather_than_analysed(client):
    events = _stream(client, {"text": "   "})
    assert events[-1][0] == "error"


def test_a_follow_up_question_is_answered_from_the_report(client):
    report = _stream(client, {"sampleId": "seventeen-minutes"})[-1][1]
    body = client.post(
        "/api/ask", json={"runId": report["runId"], "question": "Pourquoi le bar est-il en rouge ?"}
    ).json()

    assert body["answerable"] is True
    assert body["answer"]
    # Un identifiant que le rapport ne contient pas ne doit pas ressortir : le
    # lien que l'interface ouvrirait pointerait dans le vide.
    known = {f["id"] for f in report["findings"]}
    assert body["entityIds"], "la réponse ne rattache la question à aucune entité"
    assert set(body["entityIds"]) <= known
    assert "inexistant" not in body["entityIds"]


def test_a_question_on_an_expired_run_is_a_404(client):
    assert client.post("/api/ask", json={"runId": "parti", "question": "?"}).status_code == 404


def test_a_screenplay_pasted_as_text_runs_like_an_uploaded_file(client, sample_script):
    events = _stream(client, {"text": sample_script.read_text(encoding="utf-8")})
    report = events[-1][1]
    assert report["stats"]["entities"] == 15

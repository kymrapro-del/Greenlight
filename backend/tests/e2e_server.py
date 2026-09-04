"""Le serveur du test de bout en bout : le vrai, avec le réseau remplacé.

Ce module est dans l'arbre de tests, jamais dans le paquet livré. C'est la
distinction qui compte : le produit n'embarque aucun mode « démonstration » qui
fabriquerait des verdicts. Ici, `greenlight.api.server` tourne tel quel — mêmes
routes, même pipeline, même sérialisation — et seuls les deux transports
sortants sont scriptés, exactement comme dans `test_api.py`.

Ce que le test de bout en bout ajoute aux tests d'API : le navigateur. Le flux
SSE lu par du vrai code client, les composants Material Web réellement montés,
la mise en page à 1440 et à 390 dp. Aucun de ces points ne casse un test
unitaire quand il régresse.

    PYTHONPATH=backend:. uvicorn tests.e2e_server:app --port 8001
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

os.environ.setdefault("FIXTURE_MODE", "replay")

from greenlight.agents.gemini import GeminiClient  # noqa: E402
from greenlight.api import server  # noqa: E402
from tests.test_pipeline import ScriptedSearch, _dual_transport  # noqa: E402


def _transport(request: dict[str, Any]) -> dict[str, Any]:
    """Les transports des tests de pipeline, plus la phase de conversation."""
    if request["schema"] == "Answer":
        # La réponse s'appuie sur la première entité que le contexte contient
        # réellement : le lien que l'interface ouvre doit pointer quelque part.
        cited = re.findall(r"--- \[([^\]]+)\]", request["prompt"])
        body = {
            "answerable": True,
            "answer": (
                "Le bar est une entreprise réelle, et la scène y place une vente de "
                "stupéfiants. C'est la combinaison des deux qui fait monter le verdict : "
                "l'existence seule serait sans conséquence.\n\n"
                "Renommer coûte une ligne aujourd'hui."
            ),
            "entity_ids": cited[:1],
        }
        return {"json": json.dumps(body), "usage": {"prompt_tokens": 400, "output_tokens": 60}}

    if request["schema"] == "ReplacementCandidates":
        return {
            "json": json.dumps({"candidates": ["The Amber Room"]}),
            "usage": {"prompt_tokens": 200, "output_tokens": 20},
        }

    return _dual_transport(request)


def build_clients() -> tuple[GeminiClient, ScriptedSearch]:
    client = GeminiClient(transport=_transport)
    client._fixtures.mode = "live"  # le faux transport remplace le réseau
    return client, ScriptedSearch()


server.build_clients = build_clients
# Les transports sont scriptés : `/api/health` doit le dire, plutôt que de
# compter les fixtures sur disque et annoncer une panne qui n'existe pas.
server.SCRIPTED_TRANSPORTS = True
app = server.app

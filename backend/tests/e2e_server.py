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
import time
from typing import Any

os.environ.setdefault("FIXTURE_MODE", "replay")

from greenlight.agents.gemini import GeminiClient
from greenlight.api import server
from greenlight.tools.parallel_search import SearchResponse, SearchResult
from tests.test_pipeline import ScriptedSearch, _dual_transport


class HostileSearch(ScriptedSearch):
    """Rend une source dont le schéma d'URL est dangereux.

    Les URL du rapport viennent du web ouvert. Un `javascript:` posé dans un
    `href` est du code exécuté au clic, dans l'origine de l'application, et le
    pipeline ne vérifie que la *présence* d'une URL dans les résultats — pas son
    schéma. Le filtre vit donc côté interface, et un test qui n'exerce que des
    URL saines n'en prouve rien.
    """

    HOSTILE_URL = "javascript:alert(document.domain)"

    def search(self, objective, search_queries, mode=None):  # type: ignore[override]
        response = super().search(objective, search_queries, mode=mode)
        return SearchResponse(
            search_id=response.search_id,
            results=[
                *response.results,
                SearchResult(
                    url=self.HOSTILE_URL,
                    title="Source au schéma dangereux",
                    excerpts=["Une source que la recherche a rapportée telle quelle."],
                ),
            ],
            mode=response.mode,
        )


# Un appel de modèle réel prend des centaines de millisecondes. Un double qui
# répond en zéro fait tenir la passe entière en 20 ms, et l'interface n'a alors
# jamais l'occasion de peindre sa progression — ce qui ferait échouer un test
# sur une promesse que le produit tient pourtant. Ce délai rapproche le double
# du vrai plutôt que d'assouplir l'assertion.
_CALL_LATENCY_S = 0.25


def _transport(request: dict[str, Any]) -> dict[str, Any]:
    """Les transports des tests de pipeline, plus la phase de conversation."""
    time.sleep(_CALL_LATENCY_S)
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

    if request["schema"] == "Classification":
        body = json.loads(_dual_transport(request)["json"])
        # Le modèle cite ce que la recherche lui a rapporté, schéma compris.
        # Le pipeline vérifie qu'une URL citée figure bien dans les résultats ;
        # celle-ci y figure. C'est précisément le cas que le filtre côté
        # interface doit attraper, et il faut donc qu'il arrive jusqu'à elle.
        if HostileSearch.HOSTILE_URL in request["prompt"] and body.get("cited_urls"):
            body["cited_urls"] = [*body["cited_urls"], HostileSearch.HOSTILE_URL]
        return {
            "json": json.dumps(body),
            "usage": {"prompt_tokens": 900, "output_tokens": 140},
        }

    return _dual_transport(request)


def build_clients() -> tuple[GeminiClient, HostileSearch]:
    client = GeminiClient(transport=_transport)
    client._fixtures.mode = "live"  # le faux transport remplace le réseau
    return client, HostileSearch()


server.build_clients = build_clients
# Les transports sont scriptés : `/api/health` doit le dire, plutôt que de
# compter les fixtures sur disque et annoncer une panne qui n'existe pas.
server.SCRIPTED_TRANSPORTS = True
app = server.app

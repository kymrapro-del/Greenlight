"""Client Parallel Search — phase 4 du pipeline.

C'est le moteur du produit, pas un greffon : vérifier si 180 entités d'un
scénario existent dans le monde réel est un problème de recherche web profonde
à grande échelle, et c'est exactement ce que Parallel fait.

Tarifs officiels (docs.parallel.ai/getting-started/pricing) :

  turbo     ~250 ms   1 $ / 1000 requêtes
  fast      ~700 ms   1 $ / 1000 requêtes
  basic     ~1 s      5 $ / 1000 requêtes
  advanced  ~3 s      5 $ / 1000 requêtes   (défaut de l'API)

D'où le routage par niveau de risque implémenté ici : `fast` pour le gros du
fan-out, `advanced` réservé aux entités ambiguës ou dépeintes défavorablement.
Un scénario de 100 pages (~180 entités) revient à ~0,20 $ au lieu de ~0,90 $,
sans perdre en qualité là où ça compte.

Transport : SDK officiel `parallel-web`, listé comme package accepté par le
règlement du hackathon. Le paramètre `client_model` est renseigné avec le
modèle Gemini consommateur — le SDK adapte alors la compression des extraits
au modèle qui va les lire.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Literal

import parallel

from greenlight.config import settings
from greenlight.tools.fixtures import FixtureStore

Mode = Literal["turbo", "fast", "basic", "advanced"]

COST_PER_REQUEST_USD: dict[str, float] = {
    "turbo": 0.001,
    "fast": 0.001,
    "basic": 0.005,
    "advanced": 0.005,
}


@dataclass
class SearchResult:
    url: str
    title: str = ""
    publish_date: str | None = None
    excerpts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.excerpts)


@dataclass
class SearchResponse:
    search_id: str
    results: list[SearchResult]
    mode: str
    requests_billed: int = 1
    warnings: Any = None

    @property
    def cost_usd(self) -> float:
        return self.requests_billed * COST_PER_REQUEST_USD.get(self.mode, 0.005)

    @property
    def is_empty(self) -> bool:
        return not self.results

    def as_context(self, max_results: int = 8, max_chars: int = 6000) -> str:
        """Résultats mis en forme pour être passés à Gemini en phase 5."""
        chunks = []
        for i, r in enumerate(self.results[:max_results], 1):
            chunks.append(f"[{i}] {r.title}\n    {r.url}\n    {r.text[:700]}")
        return "\n\n".join(chunks)[:max_chars]


class ParallelSearch:
    """Façade unique sur la Search API, avec fixtures et suivi du coût réel."""

    def __init__(self, default_mode: Mode = "fast", timeout: float = 30.0) -> None:
        self.default_mode: Mode = default_mode
        self.timeout = timeout
        self._fixtures = FixtureStore("parallel_search")
        self._client: parallel.Parallel | None = None
        # Compteurs cumulés sur la durée de vie de l'instance : c'est ce qui
        # alimente le chiffre mesuré affiché dans le rapport et la démo. Le
        # fan-out de la phase 4 les incrémente depuis plusieurs threads, d'où le
        # verrou : un chiffre annoncé doit tenir sous vérification.
        self._lock = threading.Lock()
        self.total_requests = 0
        self.total_cost_usd = 0.0

    @property
    def client(self) -> parallel.Parallel:
        """Client SDK instancié à la demande : en mode replay, aucune clé n'est
        nécessaire et aucun client n'est créé."""
        if self._client is None:
            self._client = parallel.Parallel(api_key=settings.require_parallel_key())
        return self._client

    def search(
        self,
        objective: str,
        search_queries: list[str],
        mode: Mode | None = None,
    ) -> SearchResponse:
        mode = mode or self.default_mode
        payload: dict[str, Any] = {
            "objective": objective,
            "search_queries": search_queries,
            "mode": mode,
            "client_model": settings.model_classify,
        }

        def do_call() -> dict[str, Any]:
            result = self.client.search(
                objective=objective,
                search_queries=search_queries,
                mode=mode,
                # Indique à Parallel quel modèle consommera les extraits :
                # la compression est adaptée en conséquence.
                client_model=settings.model_classify,
                timeout=self.timeout,
            )
            return result.model_dump(mode="json")

        raw = self._fixtures.call(payload, do_call)

        billed = 1
        for u in raw.get("usage") or []:
            if u.get("name") == "sku_search":
                billed = int(u.get("count", 1))

        response = SearchResponse(
            search_id=raw.get("search_id", ""),
            results=[
                SearchResult(
                    url=r.get("url", ""),
                    title=r.get("title", ""),
                    publish_date=r.get("publish_date"),
                    excerpts=r.get("excerpts") or [],
                )
                for r in raw.get("results") or []
            ],
            mode=mode,
            requests_billed=billed,
            warnings=raw.get("warnings"),
        )

        # En replay, rien n'a été facturé : ne pas gonfler le compteur.
        if self._fixtures.mode != "replay":
            with self._lock:
                self.total_requests += response.requests_billed
                self.total_cost_usd += response.cost_usd

        return response

    def usage_summary(self) -> dict[str, float | int]:
        with self._lock:
            return {
                "requests": self.total_requests,
                "cost_usd": round(self.total_cost_usd, 4),
                "fixture_mode": self._fixtures.mode,
            }

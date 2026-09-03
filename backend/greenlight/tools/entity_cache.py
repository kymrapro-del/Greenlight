"""Cache global de recherche, par entité.

À ne pas confondre avec `tools.fixtures`, qui est un harnais de développement :
celui-là rejoue une réponse pour un payload identique, pendant qu'on itère.
Ce cache-ci est un mécanisme de production, et il répond à une autre question —
*« a-t-on déjà cherché cette entité, pour n'importe quel scénario ? »*

C'est le levier économique principal du produit. Les mêmes entités reviennent
d'un scénario à l'autre : Coca-Cola, le NYPD, Mercy General, Chicago Tribune.
Un cache par utilisateur ou par projet n'apporterait presque rien ; un cache
global fait tomber le coût marginal de chaque nouveau scénario.

La clé est `entity.id`, c'est-à-dire `type:nom-canonicalisé`. Deux propriétés en
découlent, et elles sont voulues :

- **elle traverse les variantes d'écriture** — `THE BLACK CAT TAVERN` et
  « the Black Cat Tavern » tapent la même entrée, parce que la phase 3 les
  canonicalise avant ;
- **elle sépare les types** — une entreprise nommée « Mercy » et un personnage
  nommé « Mercy » ne partagent pas leurs résultats, ce qui serait faux.

L'implémentation par défaut est en mémoire, pour le processus courant. Le
backing Firestore décrit dans l'architecture implémente la même interface :
c'est le point d'extension, pas une réécriture.
"""

from __future__ import annotations

import threading
import time
from typing import Protocol

from greenlight.models import Entity
from greenlight.tools.parallel_search import SearchResponse

# Une recherche de clearance vieillit : une entreprise ouvre, un procès sort.
# Trente jours est le compromis retenu dans l'architecture.
DEFAULT_TTL_S = 30 * 24 * 3600


class CacheBackend(Protocol):
    """Le contrat que Firestore devra remplir pour prendre le relais."""

    def get(self, key: str) -> SearchResponse | None: ...

    def put(self, key: str, response: SearchResponse) -> None: ...


class InMemoryCache:
    """Backing par défaut. Sûr entre threads : le fan-out y tape en parallèle."""

    def __init__(self, ttl_s: float = DEFAULT_TTL_S) -> None:
        self.ttl_s = ttl_s
        self._lock = threading.Lock()
        self._entries: dict[str, tuple[float, SearchResponse]] = {}

    def get(self, key: str) -> SearchResponse | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            stored_at, response = entry
            if time.monotonic() - stored_at > self.ttl_s:
                # Périmée : on la retire plutôt que de la servir.
                del self._entries[key]
                return None
            return response

    def put(self, key: str, response: SearchResponse) -> None:
        with self._lock:
            self._entries[key] = (time.monotonic(), response)

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


class EntityCache:
    """Façade avec statistiques. Le taux de hit est un chiffre qu'on annonce."""

    def __init__(self, backend: CacheBackend | None = None) -> None:
        # `is not None`, jamais `or` : un backing vide définit `__len__` et serait
        # donc falsy, ce qui le ferait remplacer en silence par un cache neuf.
        self.backend: CacheBackend = backend if backend is not None else InMemoryCache()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(entity: Entity) -> str:
        # `entity.id` vaut déjà `type:nom-canonicalisé` — la clé demandée par
        # l'architecture, sans recalcul ni risque de divergence.
        return entity.id

    def get(self, entity: Entity) -> SearchResponse | None:
        response = self.backend.get(self.key(entity))
        with self._lock:
            if response is None:
                self.misses += 1
            else:
                self.hits += 1
        return response

    def put(self, entity: Entity, response: SearchResponse) -> None:
        self.backend.put(self.key(entity), response)

    def stats(self) -> dict[str, float | int]:
        with self._lock:
            total = self.hits + self.misses
            return {
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(self.hits / total, 3) if total else 0.0,
            }

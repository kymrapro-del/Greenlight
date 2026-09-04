"""Les passes de clearance produites par le serveur, gardées en mémoire.

Une passe sert trois fois après son calcul : l'interface la recharge, une
question de suivi s'y ancre, et une réécriture s'y compare pour ne réanalyser
que ce qui a bougé. Il faut donc la conserver.

**En mémoire, et pas en base.** L'instance sert la démonstration : un dictionnaire
protégé par un verrou fait exactement le travail, sans dépendance, sans coût, et
sans le décalage entre un schéma Firestore et ce que rend le pipeline. La limite
est réelle et assumée : un redémarrage vide le store, et deux instances ne
partagent rien. C'est écrit ici plutôt que découvert en production, et le jour où
plusieurs instances tournent, seul ce module change.

Le nombre de passes est plafonné. Un scénario long tient en mémoire une fois ;
cent le font tomber.
"""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from greenlight.pipeline import ClearanceRun


@dataclass
class StoredRun:
    id: str
    payload: dict[str, Any]
    run: ClearanceRun
    source_text: str
    # Les questions déjà posées sur cette passe, pour que le fil garde son
    # contexte d'un tour à l'autre.
    history: list[tuple[str, str]] = field(default_factory=list)


class RunStore:
    def __init__(self, capacity: int = 24) -> None:
        self._runs: OrderedDict[str, StoredRun] = OrderedDict()
        self._lock = threading.Lock()
        self._capacity = capacity

    def add(self, payload: dict[str, Any], run: ClearanceRun, source_text: str) -> StoredRun:
        stored = StoredRun(
            id=uuid.uuid4().hex[:12], payload=payload, run=run, source_text=source_text
        )
        stored.payload["runId"] = stored.id
        with self._lock:
            self._runs[stored.id] = stored
            while len(self._runs) > self._capacity:
                self._runs.popitem(last=False)
        return stored

    def get(self, run_id: str) -> StoredRun | None:
        with self._lock:
            stored = self._runs.get(run_id)
            if stored is not None:
                # Une passe consultée est une passe vivante : elle ne doit pas
                # être la prochaine évincée.
                self._runs.move_to_end(stored.id)
            return stored

    def remember(self, run_id: str, question: str, answer: str) -> None:
        with self._lock:
            stored = self._runs.get(run_id)
            if stored is not None:
                stored.history.append((question, answer))
                del stored.history[:-6]

    def __len__(self) -> int:
        with self._lock:
            return len(self._runs)


store = RunStore()

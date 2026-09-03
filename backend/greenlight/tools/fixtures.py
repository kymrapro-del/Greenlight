"""Harnais d'enregistrement / rejeu des appels réseau.

Raison d'être : le budget Parallel est fini (25 $ de crédits). Sans ce harnais,
chaque itération d'UI ou de pipeline consomme des crédits pour rien, puisqu'on
rappelle l'API avec exactement les mêmes entités.

Trois modes, pilotés par FIXTURE_MODE :

  live    appelle l'API réelle, ne stocke rien
  record  appelle l'API réelle ET écrit la réponse sur disque
  replay  lit uniquement le disque — aucun appel réseau, aucun crédit consommé

Le workflow : un passage en `record` sur le scénario de démonstration, puis
tout le reste de la semaine en `replay`. Les tests tournent en `replay`,
donc la CI ne coûte jamais rien et reste déterministe.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from greenlight.config import settings


class FixtureMiss(RuntimeError):
    """Levée en mode replay quand aucune fixture n'existe pour cette clé."""


class FixtureStore:
    def __init__(self, namespace: str, mode: str | None = None, root: Path | None = None) -> None:
        self.namespace = namespace
        self.mode = (mode or settings.fixture_mode).lower()
        self.root = (root or settings.fixture_dir) / namespace
        if self.mode not in {"live", "record", "replay"}:
            raise ValueError(f"FIXTURE_MODE invalide : {self.mode!r}")

    @staticmethod
    def key(payload: dict[str, Any]) -> str:
        """Clé stable et lisible : le hash du payload canonicalisé."""
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def call(self, payload: dict[str, Any], fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        """Exécute `fn` ou renvoie la réponse mémorisée, selon le mode."""
        key = self.key(payload)
        path = self._path(key)

        if self.mode == "replay":
            if not path.exists():
                raise FixtureMiss(
                    f"Aucune fixture {self.namespace}/{key}.json pour ce payload.\n"
                    f"Rejoue une fois avec FIXTURE_MODE=record pour l'enregistrer.\n"
                    f"Payload : {json.dumps(payload, ensure_ascii=False)[:300]}"
                )
            return json.loads(path.read_text(encoding="utf-8"))["response"]

        if self.mode == "record" and path.exists():
            # Déjà enregistré : inutile de repayer.
            return json.loads(path.read_text(encoding="utf-8"))["response"]

        response = fn()

        if self.mode == "record":
            self.root.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {"payload": payload, "response": response}, ensure_ascii=False, indent=2
                ),
                encoding="utf-8",
            )

        return response

    def stats(self) -> dict[str, int]:
        if not self.root.exists():
            return {"fixtures": 0}
        return {"fixtures": len(list(self.root.glob("*.json")))}

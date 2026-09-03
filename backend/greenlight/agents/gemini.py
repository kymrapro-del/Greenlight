"""Transport Gemini — sortie structurée, fixtures, comptage réel des tokens.

Un seul point d'entrée pour tous les appels au modèle. Trois raisons :

1. SORTIE STRUCTURÉE STRICTE
   Le pipeline ne parse jamais de prose. Chaque appel déclare un
   `responseSchema` pydantic et reçoit du JSON conforme, ou lève. Pas de
   post-traitement heuristique, pas de « le modèle a répondu à côté ».

2. FIXTURES
   Même logique que pour Parallel : un passage en `record`, puis toute la
   semaine en `replay`. Les tests et la CI ne consomment jamais un token.

3. COÛT MESURÉ
   `usage_metadata` est agrégé à chaque appel. Le chiffre affiché dans la démo
   est mesuré, pas estimé. Les prix au million de tokens sont lus dans
   l'environnement : tant qu'ils ne sont pas renseignés, on rapporte des tokens
   et aucun dollar — jamais un montant inventé.

Vertex AI ou AI Studio selon `GOOGLE_GENAI_USE_VERTEXAI` : même SDK, même code,
un seul drapeau. On développe sur le free tier AI Studio et on bascule sur
Vertex pour le déploiement final.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from greenlight.config import settings
from greenlight.tools.fixtures import FixtureStore

T = TypeVar("T", bound=BaseModel)

# Transport brut : reçoit la requête canonicalisée, rend la réponse brute.
# Injectable, ce qui permet de tester le pipeline sans SDK ni réseau.
Transport = Callable[[dict[str, Any]], dict[str, Any]]


class GeminiError(RuntimeError):
    """Le modèle n'a pas rendu de JSON conforme au schéma demandé."""


class GeminiClient:
    def __init__(self, transport: Transport | None = None, namespace: str = "gemini") -> None:
        self._transport = transport
        self._fixtures = FixtureStore(namespace)
        self._client: genai.Client | None = None
        self.prompt_tokens = 0
        self.output_tokens = 0
        self.calls = 0

    # -- client SDK ------------------------------------------------------

    @property
    def client(self) -> genai.Client:
        """Instancié à la demande : en mode replay, aucune identification requise."""
        if self._client is None:
            if settings.use_vertex:
                if not settings.project:
                    raise GeminiError(
                        "GOOGLE_CLOUD_PROJECT absent alors que GOOGLE_GENAI_USE_VERTEXAI=true."
                    )
                self._client = genai.Client(
                    vertexai=True, project=settings.project, location=settings.location
                )
            else:
                self._client = genai.Client(api_key=settings.require_google_api_key())
        return self._client

    def _live_call(self, request: dict[str, Any], schema: type[BaseModel]) -> dict[str, Any]:
        response = self.client.models.generate_content(
            model=request["model"],
            contents=request["prompt"],
            config=types.GenerateContentConfig(
                system_instruction=request["system"],
                response_mime_type="application/json",
                response_schema=schema,
                # Une tâche d'extraction n'a aucune raison d'être créative, et
                # la démo doit être reproductible à l'identique.
                temperature=request["temperature"],
            ),
        )
        usage = response.usage_metadata
        return {
            "json": response.text or "",
            "usage": {
                "prompt_tokens": getattr(usage, "prompt_token_count", 0) or 0,
                "output_tokens": getattr(usage, "candidates_token_count", 0) or 0,
            },
        }

    # -- appel structuré -------------------------------------------------

    def structured(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        schema: type[T],
        temperature: float = 0.0,
    ) -> T:
        """Un appel, un schéma, une instance validée. Lève sinon."""
        request = {
            "model": model,
            "system": system,
            "prompt": prompt,
            "schema": schema.__name__,
            "temperature": temperature,
        }

        def do_call() -> dict[str, Any]:
            if self._transport is not None:
                return self._transport(request)
            return self._live_call(request, schema)

        raw = self._fixtures.call(request, do_call)

        usage = raw.get("usage") or {}
        # En replay rien n'a été consommé : ne pas gonfler le compteur.
        if self._fixtures.mode != "replay":
            self.calls += 1
            self.prompt_tokens += int(usage.get("prompt_tokens", 0))
            self.output_tokens += int(usage.get("output_tokens", 0))

        payload = raw.get("json", "")
        try:
            data = json.loads(payload) if isinstance(payload, str) else payload
            return schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise GeminiError(
                f"Réponse non conforme à {schema.__name__} : {exc}\n"
                f"Charge utile : {str(payload)[:400]}"
            ) from exc

    # -- coût ------------------------------------------------------------

    def usage_summary(self) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "output_tokens": self.output_tokens,
            "fixture_mode": self._fixtures.mode,
        }
        cost = self.cost_usd()
        if cost is not None:
            summary["cost_usd"] = round(cost, 4)
        return summary

    def cost_usd(self) -> float | None:
        """None tant que les prix ne sont pas renseignés dans l'environnement.

        Un montant inventé serait pire que pas de montant : le chiffre annoncé
        dans la démo doit tenir sous vérification.
        """
        if not (settings.price_in_per_mtok or settings.price_out_per_mtok):
            return None
        return (
            self.prompt_tokens * settings.price_in_per_mtok
            + self.output_tokens * settings.price_out_per_mtok
        ) / 1_000_000

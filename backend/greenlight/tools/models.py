"""Quels modèles ce projet peut réellement utiliser.

    python -m greenlight.tools.models

Les grilles tarifaires publiées bougent, et les comparatifs de seconde main sont
souvent périmés ou faux. Cette commande interroge l'API avec tes propres
identifiants : elle rend la liste que ton projet voit vraiment, ce qui est la
seule qui décide.

Elle ne dit pas les prix — l'API ne les expose pas. Elle dit ce qui existe, ce
qui accepte la génération de contenu, et si les modèles configurés dans `.env`
sont bien disponibles. C'est la moitié de la question qu'on peut trancher sans
se tromper ; l'autre moitié se lit sur la console de facturation.
"""

from __future__ import annotations

import sys

from greenlight.config import settings


def list_models() -> list[dict[str, str]]:
    """Modèles visibles depuis les identifiants courants."""
    from google import genai

    client = (
        genai.Client(vertexai=True, project=settings.project, location=settings.location)
        if settings.use_vertex
        else genai.Client(api_key=settings.require_google_api_key())
    )

    out = []
    for model in client.models.list():
        actions = getattr(model, "supported_actions", None) or []
        # On ne garde que ce qui sait générer du contenu : les modèles
        # d'embedding ou de comptage ne concernent pas ce pipeline.
        if actions and "generateContent" not in actions:
            continue
        out.append(
            {
                "name": (model.name or "").removeprefix("models/"),
                "display": model.display_name or "",
                "input_limit": str(getattr(model, "input_token_limit", "") or ""),
            }
        )
    return sorted(out, key=lambda m: m["name"])


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        models = list_models()
    except Exception as exc:
        print(f"Impossible d'interroger l'API : {type(exc).__name__} — {exc}")
        print("Renseigne .env (GOOGLE_API_KEY ou GOOGLE_CLOUD_PROJECT) puis réessaie.")
        return 1

    print(f"{len(models)} modèles de génération disponibles :\n")
    for model in models:
        limit = f"  ({model['input_limit']} tokens d'entrée)" if model["input_limit"] else ""
        print(f"  {model['name']:<40} {model['display']}{limit}")

    available = {m["name"] for m in models}
    print("\nModèles configurés dans .env :")
    for label, configured in (
        ("extraction", settings.model_extract),
        ("classification", settings.model_classify),
    ):
        mark = "✓ disponible" if configured in available else "✗ ABSENT de la liste ci-dessus"
        print(f"  {label:<15} {configured:<28} {mark}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

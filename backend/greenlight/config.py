"""Configuration centralisée. Lue une fois, injectée partout."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    # --- Google Cloud ---
    project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    use_vertex: bool = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true").lower() == "true"

    # Flash pour l'extraction (gros volume, tâche structurée),
    # Pro pour la classification (jugement sur le contexte de dépiction).
    model_extract: str = os.getenv("GEMINI_MODEL_EXTRACT", "gemini-3.1-flash")
    model_classify: str = os.getenv("GEMINI_MODEL_CLASSIFY", "gemini-3-pro")

    # --- Parallel ---
    parallel_api_key: str = os.getenv("PARALLEL_API_KEY", "")

    # --- Fixtures ---
    fixture_mode: str = os.getenv("FIXTURE_MODE", "replay")  # live | record | replay
    fixture_dir: Path = REPO_ROOT / os.getenv("FIXTURE_DIR", "fixtures")

    def require_parallel_key(self) -> str:
        if not self.parallel_api_key:
            raise RuntimeError(
                "PARALLEL_API_KEY absent. Copie .env.example vers .env et renseigne la clé, "
                "ou passe FIXTURE_MODE=replay pour travailler hors ligne."
            )
        return self.parallel_api_key


settings = Settings()

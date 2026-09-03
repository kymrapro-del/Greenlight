"""Garde-fou global de la suite de tests.

Force le mode replay AVANT tout import de `greenlight`, pour qu'aucun test ne
puisse toucher une API réelle ni consommer de crédits — ni en local, ni en CI.
"""

import os
from pathlib import Path

os.environ["FIXTURE_MODE"] = "replay"
os.environ.pop("PARALLEL_API_KEY", None)

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def sample_script() -> Path:
    return REPO_ROOT / "samples" / "seventeen_minutes.fountain"


@pytest.fixture(scope="session")
def sample_script_v2() -> Path:
    """Réécriture du scénario de démonstration : deux entités renommées, un
    numéro corrigé, une entité redépeinte, une scène ajoutée."""
    return REPO_ROOT / "samples" / "seventeen_minutes_v2.fountain"

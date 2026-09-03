"""Modèle de données GREENLIGHT.

Ces schémas servent trois rôles à la fois :
  - contrat de sortie structurée pour Gemini (responseSchema)
  - forme des documents Firestore
  - contrat de l'API HTTP

Un seul endroit à modifier. Ne pas dupliquer ces définitions ailleurs.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------
# Taxonomie
# --------------------------------------------------------------------------


class EntityType(str, Enum):
    """Catégories recensées par un rapport de clearance professionnel."""

    CHARACTER_NAME = "CHARACTER_NAME"
    BUSINESS = "BUSINESS"
    PRODUCT_BRAND = "PRODUCT_BRAND"
    PHONE = "PHONE"
    ADDRESS = "ADDRESS"
    LICENSE_PLATE = "LICENSE_PLATE"
    URL_EMAIL = "URL_EMAIL"
    SONG = "SONG"
    ARTWORK = "ARTWORK"
    PUBLICATION = "PUBLICATION"
    INSTITUTION = "INSTITUTION"
    REAL_PERSON = "REAL_PERSON"
    REAL_EVENT = "REAL_EVENT"
    SPORTS_TEAM = "SPORTS_TEAM"
    VEHICLE = "VEHICLE"
    GOVERNMENT_AGENCY = "GOVERNMENT_AGENCY"


class ContextTier(str, Enum):
    """Comment l'entité est dépeinte dans la scène.

    C'est le multiplicateur de risque, et le cœur du produit : la même entité
    réelle est inoffensive en contexte neutre et devient un risque juridique
    dès qu'un personnage y commet un acte répréhensible.
    """

    NEUTRAL = "neutral"
    UNFLATTERING = "unflattering"
    ILLEGAL = "illegal"


class Verdict(str, Enum):
    CLEAR = "CLEAR"
    CAUTION = "CAUTION"
    CHANGE_RECOMMENDED = "CHANGE_RECOMMENDED"
    LICENSE_REQUIRED = "LICENSE_REQUIRED"
    UNRESOLVED = "UNRESOLVED"


# --------------------------------------------------------------------------
# Scénario
# --------------------------------------------------------------------------


class Scene(BaseModel):
    id: str
    number: int
    heading: str
    int_ext: str | None = None  # INT / EXT / INT-EXT
    location: str | None = None
    time_of_day: str | None = None
    action: str = ""
    dialogue: list[str] = Field(default_factory=list)
    characters: list[str] = Field(default_factory=list)
    page_start: float | None = None

    def as_context(self, max_chars: int = 4000) -> str:
        """Texte de la scène tel qu'envoyé à Gemini."""
        body = self.action
        if self.dialogue:
            body += "\n" + "\n".join(self.dialogue)
        return f"{self.heading}\n{body}"[:max_chars]


class Draft(BaseModel):
    id: str
    version: int
    source_path: str
    fmt: str  # fountain | fdx
    title: str | None = None
    scenes: list[Scene] = Field(default_factory=list)
    parent_draft_id: str | None = None


# --------------------------------------------------------------------------
# Entités et findings
# --------------------------------------------------------------------------


class Occurrence(BaseModel):
    scene_id: str
    scene_number: int
    context_tier: ContextTier = ContextTier.NEUTRAL
    quote: str = ""  # extrait où l'entité apparaît, pour l'affichage


class ExtractedEntity(BaseModel):
    """Sortie brute de la phase 2 (une scène, une entité)."""

    name: str
    type: EntityType
    context_tier: ContextTier = ContextTier.NEUTRAL
    quote: str = ""


class SceneExtraction(BaseModel):
    """responseSchema de la phase 2. Gemini répond exactement ça."""

    entities: list[ExtractedEntity] = Field(default_factory=list)


class Entity(BaseModel):
    """Entité canonique après dédup à l'échelle du scénario (phase 3)."""

    id: str
    canonical_name: str
    type: EntityType
    aliases: list[str] = Field(default_factory=list)
    occurrences: list[Occurrence] = Field(default_factory=list)

    @property
    def worst_context(self) -> ContextTier:
        order = [ContextTier.NEUTRAL, ContextTier.UNFLATTERING, ContextTier.ILLEGAL]
        return max(
            (o.context_tier for o in self.occurrences), key=order.index, default=ContextTier.NEUTRAL
        )


class Citation(BaseModel):
    url: str
    title: str = ""
    excerpt: str = ""
    publish_date: str | None = None


class Finding(BaseModel):
    """Verdict de clearance pour une entité dans un draft donné."""

    id: str
    entity_id: str
    draft_id: str
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    citations: list[Citation] = Field(default_factory=list)
    suggested_replacement: str | None = None
    replacement_verified: bool = False
    prompt_version: str = "v1"


class Classification(BaseModel):
    """responseSchema de la phase 5."""

    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    cited_urls: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Job
# --------------------------------------------------------------------------


class JobState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class Job(BaseModel):
    id: str
    draft_id: str
    state: JobState = JobState.PENDING
    phase: str = "ingest"
    total: int = 0
    done: int = 0
    failed: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    # Coût réel mesuré, agrégé depuis le champ `usage` des réponses Parallel.
    search_requests: int = 0
    search_cost_usd: float = 0.0

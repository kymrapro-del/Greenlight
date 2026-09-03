"""Parser Fountain — phase 1 du pipeline.

Fountain est le format texte standard d'écriture de scénario (fountain.io).
On le privilégie au PDF : le PDF de scénario est un piège chronophage et
n'apporte aucun point au jury.

Ce parser est volontairement pragmatique. Il couvre ce dont le pipeline a
besoin — le découpage en scènes, l'action, les dialogues, les personnages —
et ignore le reste de la spec (dual dialogue, lyrics, sections, centrage).
"""

from __future__ import annotations

import re
from pathlib import Path

from greenlight.models import Draft, Scene

# Une page de scénario ≈ 55 lignes en Courier 12pt.
LINES_PER_PAGE = 55

_BONEYARD = re.compile(r"/\*.*?\*/", re.DOTALL)
_NOTE = re.compile(r"\[\[.*?\]\]", re.DOTALL)

# "INT. BAR - NIGHT", "EXT./INT. CAR - DAY", "I/E. HOUSE", ou forcé par un point : ".BLACK"
_SCENE_HEADING = re.compile(
    r"^(?:\.(?!\.)|(?:INT|EXT|EST|INT\.?/EXT|EXT\.?/INT|I/E)[\.\s/])",
    re.IGNORECASE,
)

# "CUT TO:", "FADE IN:", "FADE OUT.", "DISSOLVE TO:", ou forcé par ">"
_TRANSITION = re.compile(
    r"^(?:>\s*.+"
    r"|[A-Z][A-Z\s]*TO:"
    r"|(?:FADE (?:IN|OUT|TO BLACK)|DISSOLVE|SMASH CUT|MATCH CUT|JUMP CUT|INTERCUT|"
    r"CUT TO BLACK|THE END)\b.*)$"
)

# "JEAN", "JEAN (V.O.)", "JEAN (CONT'D)", ou forcé par "@"
_CHARACTER = re.compile(r"^(?:@.+|[A-Z][A-Z0-9\s\.\'\-]*(?:\s*\([^)]*\))?)$")

_PARENTHETICAL = re.compile(r"^\(.*\)$")

# "INT. MERCY GENERAL - EMERGENCY ROOM - NIGHT"
#  ^int_ext  ^-------- location --------^   ^time
_TIME_SUFFIXES = (
    "DAY",
    "NIGHT",
    "MORNING",
    "EVENING",
    "AFTERNOON",
    "DAWN",
    "DUSK",
    "CONTINUOUS",
    "LATER",
    "MOMENTS LATER",
    "SAME",
    "NOON",
    "MIDNIGHT",
)


def _strip_comments(text: str) -> str:
    text = _BONEYARD.sub("", text)
    return _NOTE.sub("", text)


def _parse_title_page(lines: list[str]) -> tuple[dict[str, str], int]:
    """Retourne (métadonnées, index de la première ligne du corps)."""
    meta: dict[str, str] = {}
    key = None
    i = 0
    for i, raw in enumerate(lines):
        line = raw.rstrip()
        if not line.strip():
            if meta:
                return meta, i + 1
            continue
        m = re.match(r"^([A-Za-z ]+):\s*(.*)$", line)
        if m:
            key = m.group(1).strip().lower()
            meta[key] = m.group(2).strip()
        elif key and line.startswith((" ", "\t")):
            meta[key] = (meta[key] + " " + line.strip()).strip()
        else:
            # Pas une page de titre : le corps commence ici.
            return meta, 0 if not meta else i
    return meta, i + 1


def _split_heading(heading: str) -> tuple[str | None, str | None, str | None]:
    """'INT. BAR LE CHAT NOIR - NIGHT' -> ('INT', 'BAR LE CHAT NOIR', 'NIGHT')."""
    h = heading.lstrip(".").strip()

    int_ext = None
    m = re.match(r"^(INT\.?/EXT|EXT\.?/INT|I/E|INT|EXT|EST)\b\.?\s*", h, re.IGNORECASE)
    if m:
        int_ext = m.group(1).upper().rstrip(".")
        h = h[m.end() :]

    time_of_day = None
    if " - " in h:
        head, _, tail = h.rpartition(" - ")
        if tail.strip().upper() in _TIME_SUFFIXES or len(tail.strip()) <= 20:
            time_of_day = tail.strip().upper()
            h = head

    return int_ext, (h.strip() or None), time_of_day


def _is_character(line: str, prev_blank: bool, next_line: str | None) -> bool:
    if not prev_blank or not next_line or not next_line.strip():
        return False
    if line.startswith("@"):
        return True
    if _TRANSITION.match(line) or _SCENE_HEADING.match(line):
        return False
    if not _CHARACTER.match(line):
        return False
    # Doit contenir au moins une lettre, et être réellement en majuscules.
    letters = [c for c in line if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def parse_fountain(
    text: str, draft_id: str = "draft-1", version: int = 1, source_path: str = ""
) -> Draft:
    """Découpe un scénario Fountain en scènes structurées."""
    lines = _strip_comments(text).replace("\r\n", "\n").split("\n")
    meta, start = _parse_title_page(lines)

    scenes: list[Scene] = []
    current: Scene | None = None
    pending_character: str | None = None

    def flush() -> None:
        nonlocal current
        if current is not None:
            current.action = current.action.strip()
            current.characters = sorted(set(current.characters))
            scenes.append(current)
            current = None

    for idx in range(start, len(lines)):
        raw = lines[idx]
        line = raw.strip()
        prev_blank = idx == start or not lines[idx - 1].strip()
        next_line = lines[idx + 1] if idx + 1 < len(lines) else None

        if not line:
            pending_character = None
            continue

        if line.startswith("==="):  # saut de page
            continue

        if _SCENE_HEADING.match(line):
            flush()
            int_ext, location, tod = _split_heading(line)
            current = Scene(
                id=f"{draft_id}-s{len(scenes) + 1}",
                number=len(scenes) + 1,
                heading=line.lstrip(".").strip(),
                int_ext=int_ext,
                location=location,
                time_of_day=tod,
                page_start=round(idx / LINES_PER_PAGE + 1, 1),
            )
            pending_character = None
            continue

        if _TRANSITION.match(line):
            pending_character = None
            continue

        if current is None:
            # Action avant toute en-tête de scène : on ouvre une scène implicite.
            current = Scene(
                id=f"{draft_id}-s1",
                number=1,
                heading="(OPENING)",
                page_start=1.0,
            )

        if _is_character(line, prev_blank, next_line):
            name = line.lstrip("@")
            name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()  # retire (V.O.), (CONT'D)
            pending_character = name
            current.characters.append(name)
            continue

        if pending_character:
            if _PARENTHETICAL.match(line):
                continue
            current.dialogue.append(f"{pending_character}: {line}")
            continue

        current.action += line + "\n"

    flush()

    return Draft(
        id=draft_id,
        version=version,
        source_path=source_path,
        fmt="fountain",
        title=meta.get("title"),
        scenes=scenes,
    )


def parse_file(path: str | Path, **kwargs) -> Draft:
    p = Path(path)
    return parse_fountain(p.read_text(encoding="utf-8"), source_path=str(p), **kwargs)

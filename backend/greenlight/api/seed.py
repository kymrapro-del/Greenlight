"""Génère le rapport de démonstration servi par l'interface.

    python -m greenlight.api.seed frontend/public/demo-report.json

Le battle plan est explicite : les juges ne vont pas déposer leur propre
scénario et attendre. L'application doit s'ouvrir sur un rapport complet et
instantané. Ce fichier est ce rapport.

Tant qu'aucun passage réel n'a été enregistré, la graine est produite par le
harnais de test et porte `placeholder: true` — l'interface l'affiche. Une fois
les fixtures enregistrées avec de vraies clés, relancer ce script sans
`--placeholder` produit le même fichier avec de vrais verdicts et de vraies
sources.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from greenlight.api.report import to_payload
from greenlight.pipeline import run_clearance

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCRIPT = REPO_ROOT / "samples" / "seventeen_minutes.fountain"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Graine du rapport de démonstration")
    parser.add_argument("out", help="chemin du fichier JSON à écrire")
    parser.add_argument("--script", default=str(DEFAULT_SCRIPT))
    parser.add_argument(
        "--against",
        metavar="SCRIPT_V1",
        help="version précédente : produit un rapport de diff plutôt qu'une passe complète",
    )
    parser.add_argument(
        "--placeholder",
        action="store_true",
        help="produit la graine depuis le harnais de test, sans toucher aux API",
    )
    parser.add_argument("--suggest", action="store_true")
    args = parser.parse_args(argv)

    if args.placeholder:
        # Le harnais de test fournit un transport scripté : aucune clé requise,
        # aucun crédit consommé, et le résultat est signalé comme tel.
        sys.path.insert(0, str(REPO_ROOT / "backend" / "tests"))
        from test_pipeline import ScriptedSearch, v2_client  # type: ignore

        def passe(script: str, draft_id: str, previous=None):
            return run_clearance(
                script,
                v2_client(),
                ScriptedSearch(),
                draft_id=draft_id,
                suggest=args.suggest,
                previous=previous,
            )
    else:

        def passe(script: str, draft_id: str, previous=None):
            return run_clearance(script, draft_id=draft_id, suggest=args.suggest, previous=previous)

    if args.against:
        # La passe sur la version précédente sert de référence : c'est elle qui
        # permet au diff de ne réanalyser que ce que la réécriture a touché.
        run = passe(args.script, "draft-2", previous=passe(args.against, "draft-1"))
    else:
        run = passe(args.script, "draft-1")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(to_payload(run, placeholder=args.placeholder), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"écrit {out} — {len(run.findings)} verdicts, placeholder={args.placeholder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

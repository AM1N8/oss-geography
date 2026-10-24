"""Small noninteractive command-line interface, powered by argparse."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ossgeo import __version__
from ossgeo.acquire import existing_store, fetch_all, get_store
from ossgeo.prepare import prepare
from ossgeo.storage import DataError
from ossgeo.validate import validate


def parser() -> argparse.ArgumentParser:
    """Describe all commands without network access or side effects."""
    result = argparse.ArgumentParser(
        prog="ossgeo",
        description="Acquisition et préparation — Geography of GitHub (2020–2025)",
    )
    result.add_argument("--version", action="version", version=__version__)
    result.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Racine du projet (défaut : répertoire courant)",
    )
    commands = result.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser(
        "fetch", help="Acquérir/vérifier un instantané, avec cache SHA-256"
    )
    fetch.add_argument(
        "--profile",
        choices=["core", "all"],
        default="core",
        help="Tables GitHub ; les trois fournisseurs sont toujours acquis",
    )
    fetch.add_argument(
        "--update",
        action="store_true",
        help="Créer un NOUVEL instantané et résoudre à nouveau les révisions",
    )
    commands.add_parser(
        "validate", help="Valider hors ligne ; code retour 1 si erreur bloquante"
    )
    commands.add_parser(
        "prepare", help="Valider puis préparer les observations 2020–2025"
    )
    commands.add_parser(
        "status", help="Afficher l'état local et vérifier tous les SHA-256 hors ligne"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    """Return shell-friendly exit codes and source-specific error diagnostics."""
    args = parser().parse_args(argv)
    try:
        root = args.root.resolve()
        if args.command == "fetch":
            store = get_store(root, update=args.update)
            print(f"Instantané : {store.manifest['snapshot']}", file=sys.stderr)
            fetch_all(store, args.profile)
            print(
                f"Acquisition {args.profile} terminée : {len(store.manifest['files'])} fichiers vérifiés."
            )
        elif args.command == "validate":
            report, _ = validate(existing_store(root))
            print(
                json.dumps(
                    {
                        k: report[k]
                        for k in (
                            "snapshot",
                            "error_count",
                            "warning_count",
                            "errors",
                            "warnings",
                        )
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return int(bool(report["errors"]))
        elif args.command == "prepare":
            print(prepare(existing_store(root)))
        else:
            store = existing_store(root)
            for record in store.manifest["files"].values():
                store.verify(record)
            print(
                json.dumps(
                    {
                        "snapshot": store.manifest["snapshot"],
                        "revisions": store.manifest["revisions"],
                        "completed_profiles": store.manifest["completed_profiles"],
                        "verified_files": len(store.manifest["files"]),
                        "bytes": sum(
                            r["size"] for r in store.manifest["files"].values()
                        ),
                    },
                    indent=2,
                )
            )
        return 0
    except (DataError, OSError, ValueError, KeyError, TypeError) as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(
            "Interrompu ; les fichiers complets restent dans le cache. Relancer la même commande.",
            file=sys.stderr,
        )
        return 130

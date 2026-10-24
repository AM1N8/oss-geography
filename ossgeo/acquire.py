"""Provider-specific acquisition, pinned Git revisions and explicit pagination."""

from __future__ import annotations

import hashlib
import re
import tomllib
import uuid
from functools import partial
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from ossgeo.storage import DataError, Json, Store, atomic_json, read_json, utc_now


def load_config(root: Path) -> Json:
    """Load the repository source configuration."""
    return tomllib.loads((root / "config/sources.toml").read_text(encoding="utf-8"))


def get_store(root: Path, *, update: bool = False) -> Store:
    """Select the current snapshot or explicitly start a new one."""
    config = load_config(root)
    fingerprint = hashlib.sha256(
        (root / "config/sources.toml").read_bytes()
    ).hexdigest()
    lock = root / "data/metadata/sources.lock.json"
    if lock.exists() and not update:
        pointer = read_json(lock)
        manifest = read_json(
            root / "data/metadata/manifests" / f"{pointer['snapshot']}.json"
        )
        if manifest["config_sha256"] != fingerprint:
            raise DataError(
                "Configuration des sources modifiée : utiliser fetch --update"
            )
    else:
        snapshot = (
            utc_now().replace(":", "").replace("+0000", "Z")
            + "-"
            + uuid.uuid4().hex[:8]
        )
        manifest = {
            "format_version": 1,
            "snapshot": snapshot,
            "created_at": utc_now(),
            "config_sha256": fingerprint,
            "config": config,
            "revisions": {},
            "files": {},
            "completed_profiles": [],
        }
        store = Store(root, manifest, **config["download"])
        store.save()
        atomic_json(lock, {"format_version": 1, "snapshot": snapshot})
    return Store(root, manifest, **config["download"])


def existing_store(root: Path) -> Store:
    """Load a snapshot without creating one or using the network."""
    if not (root / "data/metadata/sources.lock.json").exists():
        raise DataError("Aucun instantané : exécuter ossgeo fetch --profile core")
    return get_store(root)


def resolve_revision(store: Store, provider: str, config: Json) -> str:
    """Resolve a Git ref once per snapshot; persist its complete commit SHA."""
    path = store.fetch(
        provider,
        "revision",
        f"https://api.github.com/repos/{config['repository']}/commits/{config['ref']}",
        "_revision.json",
        "json",
        config["terms"],
    )
    revision = read_json(path).get("sha", "")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise DataError(f"{provider} : SHA Git complet absent de {path}")
    if provider in store.manifest["revisions"]:
        if revision != store.manifest["revisions"][provider]:
            raise DataError(f"{provider} : révision différente de l'instantané épinglé")
        return str(revision)
    store.manifest["revisions"][provider] = revision
    store.manifest["files"][f"{provider}:revision"]["revision"] = revision
    store.save()
    return str(revision)


def check_page(value: Any, page: int) -> tuple[Json, list[Json]]:
    """Validate the World Bank response envelope, including API error payloads."""
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not isinstance(value[0], dict)
        or not isinstance(value[1], list)
    ):
        raise DataError(f"World Bank page {page} : enveloppe API inattendue")
    header, rows = value
    try:
        current, pages, total, per_page = (
            int(header[field]) for field in ("page", "pages", "total", "per_page")
        )
    except (KeyError, TypeError, ValueError) as error:
        raise DataError(f"World Bank page {page} : pagination invalide") from error
    if (
        current != page
        or not 1 <= page <= pages <= 10000
        or per_page <= 0
        or total < 0
        or pages != max(1, (total + per_page - 1) // per_page)
        or len(rows) != min(per_page, max(0, total - (page - 1) * per_page))
        or not all(isinstance(row, dict) for row in rows)
    ):
        raise DataError(f"World Bank page {page} : pagination incohérente")
    return header, rows


def combine_pages(values: list[Any]) -> list[Json]:
    """Check completeness, totals and update stability across all retained pages."""
    rows: list[Json] = []
    first: Json | None = None
    for number, value in enumerate(values, 1):
        header, batch = check_page(value, number)
        if first is None:
            first = header
        for field in ("pages", "total", "per_page", "lastupdated", "sourceid"):
            if str(header.get(field)) != str(first.get(field)):
                raise DataError(
                    f"World Bank : métadonnées variables entre pages ({field})"
                )
        rows.extend(batch)
    if (
        first is None
        or len(values) != int(first["pages"])
        or len(rows) != int(first["total"])
    ):
        raise DataError("World Bank : pagination incomplète")
    return rows


def fetch_pages(
    store: Store, name: str, endpoint: str, params: Json, config: Json
) -> None:
    """Fetch every numbered page, retaining each original JSON response."""
    values: list[Any] = []
    page, pages = 1, 1
    while page <= pages:
        url = f"{config['base_url']}/{endpoint}?" + urlencode(
            {**params, "format": "json", "per_page": config["per_page"], "page": page}
        )
        path = store.fetch(
            "world_bank",
            f"{name}/page-{page:04d}",
            url,
            f"{name}/page-{page:04d}.json",
            "json",
            config["terms"],
            checker=partial(check_page_file, page=page),
        )
        value = read_json(path)
        header, _ = check_page(value, page)
        pages = int(header["pages"])
        values.append(value)
        page += 1
    combine_pages(values)


def check_page_file(path: Path, *, page: int) -> None:
    """Check an API page before promoting its temporary file."""
    check_page(read_json(path), page)


def fetch_all(store: Store, profile: str) -> None:
    """Acquire a profile and all contextual sources for the selected snapshot."""
    for record in store.manifest["files"].values():
        if (store.root / record["path"]).exists():
            store.verify(record)
    config = store.manifest["config"]
    gh = config["github"]
    revision = resolve_revision(store, "github", gh)

    def github_file(source_id: str, path: str, kind: str) -> Path:
        return store.fetch(
            "github",
            source_id,
            f"https://raw.githubusercontent.com/{gh['repository']}/{revision}/{path}",
            path,
            kind,
            gh["terms"],
            revision,
        )

    schema_path = github_file("datapackage.json", "datapackage.json", "json")
    tree_path = store.fetch(
        "github",
        "tree",
        f"https://api.github.com/repos/{gh['repository']}/git/trees/{revision}?recursive=1",
        "_tree.json",
        "json",
        gh["terms"],
        revision,
    )
    tree = read_json(tree_path)
    if tree.get("truncated"):
        raise DataError("Arborescence GitHub tronquée")
    available = {item["path"] for item in tree["tree"] if item["type"] == "blob"}
    resources = {item["name"]: item for item in read_json(schema_path)["resources"]}
    tables = gh["core"] + (gh["optional"] if profile == "all" else [])
    tables += sorted(name for name in resources if name.startswith("distinct_"))
    for name in tables:
        resource_path = resources[name]["path"]
        # The published datapackage currently has stale representativeness paths.
        if resource_path not in available and name.startswith("distinct_"):
            resource_path = f"representativeness_data/{name}.csv"
        if resource_path not in available:
            raise DataError(f"Chemin GitHub introuvable à {revision} : {resource_path}")
        github_file(name, resource_path, "csv")
    for path in gh["support"]:
        github_file(path, path, "json" if path.endswith(".json") else "text")

    ne = config["natural_earth"]
    ne_revision = resolve_revision(store, "natural_earth", ne)
    for path in [ne["path"], *ne["support"]]:
        store.fetch(
            "natural_earth",
            path,
            f"https://raw.githubusercontent.com/{ne['repository']}/{ne_revision}/{path}",
            path,
            "geojson" if path.endswith(".geojson") else "text",
            ne["terms"],
            ne_revision,
        )
    wb = config["world_bank"]
    fetch_pages(store, "economies", "country", {}, wb)
    fetch_pages(store, "indicator", f"indicator/{wb['indicator']}", {}, wb)
    study = config["study"]
    fetch_pages(
        store,
        "population",
        f"country/all/indicator/{wb['indicator']}",
        {"date": f"{study['start_year']}:{study['end_year']}", "source": 2},
        wb,
    )
    completed = set(store.manifest["completed_profiles"])
    completed.add("core")
    if profile == "all":
        completed.add("all")
    for record in store.manifest["files"].values():
        store.verify(record)
    store.manifest["completed_profiles"] = sorted(completed)
    store.save()


def wb_rows(store: Store, name: str) -> list[Json]:
    """Read and revalidate saved pages without contacting the API."""
    records = sorted(
        (
            r
            for r in store.manifest["files"].values()
            if r["provider"] == "world_bank" and r["source_id"].startswith(name + "/")
        ),
        key=lambda r: int(r["source_id"].rsplit("-", 1)[1]),
    )
    return combine_pages([read_json(store.root / record["path"]) for record in records])

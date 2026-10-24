"""Atomic, checksum-verified HTTPS downloads and snapshot manifests."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

Json = dict[str, Any]


class DataError(Exception):
    """A source, snapshot or validation failed an explicit contract."""


def utc_now() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC).isoformat()


def sha256(path: Path) -> str:
    """Hash a file without loading it into memory."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path) -> Any:
    """Read a UTF-8 JSON document."""
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_bytes(path: Path, content: bytes) -> None:
    """Replace a small generated file atomically on the same filesystem."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".part")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def atomic_json(path: Path, content: Any) -> None:
    """Write stable, readable JSON atomically."""
    atomic_bytes(
        path,
        (
            json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode(),
    )


class HttpsRedirect(urllib.request.HTTPRedirectHandler):
    """Disallow redirects that downgrade HTTPS."""

    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> Any:
        if not newurl.startswith("https://"):
            raise DataError(f"Redirection non HTTPS : {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_https(request: urllib.request.Request, *, timeout: int) -> Any:
    """Open an HTTPS request with downgrade protection."""
    return urllib.request.build_opener(HttpsRedirect()).open(request, timeout=timeout)


def check_payload(path: Path, kind: str) -> None:
    """Reject empty files, HTML errors and malformed structured responses."""
    if path.stat().st_size == 0:
        raise DataError("Réponse vide")
    with path.open("rb") as stream:
        prefix = stream.read(1024).lstrip().lower()
    if prefix.startswith((b"<!doctype html", b"<html")):
        raise DataError("Page HTML reçue à la place des données")
    if kind in {"json", "geojson"}:
        value = read_json(path)
        if kind == "geojson" and (
            not isinstance(value, dict) or value.get("type") != "FeatureCollection"
        ):
            raise DataError("GeoJSON attendu : FeatureCollection")
    if kind == "csv" and b"," not in prefix.split(b"\n", 1)[0]:
        raise DataError("En-tête CSV inattendu")


class Store:
    """A single immutable raw snapshot, with resumable acquisitions."""

    def __init__(
        self, root: Path, manifest: Json, timeout: int = 60, attempts: int = 3
    ) -> None:
        self.root = root
        self.manifest = manifest
        self.timeout = timeout
        self.attempts = attempts
        self.path = root / "data/metadata/manifests" / f"{manifest['snapshot']}.json"

    def save(self) -> None:
        """Persist acquisition progress after each successful file."""
        atomic_json(self.path, self.manifest)

    def verify(self, record: Json) -> None:
        """Fail if a recorded raw file is missing, truncated or modified."""
        path = self.root / record["path"]
        if not path.is_file():
            raise DataError(f"Fichier absent : {record['path']}")
        if path.stat().st_size != record["size"] or sha256(path) != record["sha256"]:
            raise DataError(f"Cache corrompu : {record['path']} (SHA-256/taille)")

    def fetch(
        self,
        provider: str,
        source_id: str,
        url: str,
        filename: str,
        kind: str,
        terms: str,
        revision: str | None = None,
        checker: Callable[[Path], None] | None = None,
    ) -> Path:
        """Download or verify a cached file; never replace recorded raw bytes.

        A missing recorded file may be restored only if its old digest matches.
        Unrecorded existing files require manual investigation, not overwriting.
        """
        if not url.startswith("https://"):
            raise DataError(f"URL non HTTPS : {url}")
        key = f"{provider}:{source_id}"
        relative = f"data/raw/{provider}/{self.manifest['snapshot']}/{filename}"
        path = self.root / relative
        records = self.manifest["files"]
        previous = records.get(key)
        if previous and (
            previous["requested_url"] != url or previous["path"] != relative
        ):
            raise DataError(f"Source modifiée sans nouvel instantané : {key}")
        if path.exists():
            if not previous:
                raise DataError(f"Fichier existant non répertorié : {relative}")
            self.verify(previous)
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".part")
            temp = Path(temporary)
            try:
                request = urllib.request.Request(
                    url, headers={"User-Agent": "ossgeo/0.1 university-data-setup"}
                )
                with os.fdopen(fd, "wb") as output:
                    with open_https(request, timeout=self.timeout) as response:
                        final_url = response.geturl()
                        if response.status != 200 or not final_url.startswith(
                            "https://"
                        ):
                            raise DataError(
                                f"Réponse HTTP inattendue : {response.status}"
                            )
                        length = response.headers.get("Content-Length")
                        while chunk := response.read(1024 * 1024):
                            output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                if length and temp.stat().st_size != int(length):
                    raise DataError("Réponse tronquée (Content-Length)")
                check_payload(temp, kind)
                if checker:
                    checker(temp)
                digest = sha256(temp)
                if previous and digest != previous["sha256"]:
                    raise DataError(
                        "Octets différents de l'instantané enregistré ; restaurer la "
                        "copie originale ou utiliser fetch --update"
                    )
                record = {
                    "provider": provider,
                    "source_id": source_id,
                    "requested_url": url,
                    "final_url": final_url,
                    "retrieved_at": utc_now(),
                    "path": relative,
                    "size": temp.stat().st_size,
                    "sha256": digest,
                    "revision": revision,
                    "api_metadata": None,
                    "terms": terms,
                }
                if provider == "world_bank":
                    record["api_metadata"] = read_json(temp)[0]
                os.replace(temp, path)
                # Keep original provenance when restoring identical bytes.
                records[key] = previous or record
                self.save()
                return path
            except (
                OSError,
                http.client.HTTPException,
                ValueError,
                DataError,
            ) as error:
                last_error = error
                if isinstance(error, DataError):
                    break
                if isinstance(error, urllib.error.HTTPError) and error.code not in {
                    408,
                    429,
                    500,
                    502,
                    503,
                    504,
                }:
                    break
                if attempt + 1 < self.attempts:
                    time.sleep(min(2**attempt, 4))
            finally:
                temp.unlink(missing_ok=True)
        raise DataError(f"{provider}/{source_id} : échec de {url} : {last_error}")

"""Offline failure, integrity, pagination and snapshot lifecycle contracts."""

import urllib.error

import pytest

from ossgeo.acquire import (
    check_page,
    combine_pages,
    existing_store,
    fetch_all,
    fetch_pages,
    get_store,
    resolve_revision,
    wb_rows,
)
from ossgeo.storage import (
    DataError,
    HttpsRedirect,
    atomic_bytes,
    check_payload,
    read_json,
    sha256,
)
from conftest import Response


def page(number, total=3, rows=None):
    return [
        {
            "page": number,
            "pages": 2,
            "total": total,
            "per_page": "2",
            "lastupdated": "2026-01-01",
        },
        (
            rows
            if rows is not None
            else ([{"id": 1}, {"id": 2}] if number == 1 else [{"id": 3}])
        ),
    ]


def test_pagination_fetch_and_original_responses(remote):
    store, calls = remote
    config = {**store.manifest["config"]["world_bank"], "per_page": 2}
    fetch_pages(store, "economies", "country", {}, config)
    assert len(wb_rows(store, "economies")) == 3
    assert ["page=1" in calls[0], "page=2" in calls[1]] == [True, True]
    records = list(store.manifest["files"].values())
    assert records[1]["api_metadata"]["lastupdated"] == "2026-01-01"
    before = list(calls)
    fetch_pages(store, "economies", "country", {}, config)
    assert calls == before


@pytest.mark.parametrize(
    "values",
    [
        [],
        [page(1)],
        [page(2)],
        [page(1), page(2, total=4)],
        [page(1), [dict(page(2)[0], lastupdated="changed"), page(2)[1]]],
    ],
)
def test_incomplete_or_changed_pagination(values):
    with pytest.raises(DataError):
        combine_pages(values)


@pytest.mark.parametrize(
    "value",
    [
        {"message": "error"},
        [],
        [{}, None],
        [{}, []],
        [dict(page(1)[0], pages=1), page(1)[1]],
        [page(1)[0], [1, 2]],
    ],
)
def test_unexpected_api_response(value):
    with pytest.raises(DataError):
        check_page(value, 1)


def test_download_failure_has_no_final_file(root, monkeypatch):
    store = get_store(root)
    store.attempts = 2
    attempts = []

    class Interrupted(Response):
        def read(self, size):
            raise OSError("SYNTHETIC interrupted connection")

    def opener(*args, **kwargs):
        attempts.append(1)
        return Interrupted(b"partial")

    monkeypatch.setattr("ossgeo.storage.open_https", opener)
    monkeypatch.setattr("ossgeo.storage.time.sleep", lambda _: None)
    with pytest.raises(DataError, match="github/synthetic"):
        store.fetch(
            "github",
            "synthetic",
            "https://example.org/data",
            "failed.csv",
            "csv",
            "terms",
        )
    assert len(attempts) == 2
    assert not list((root / "data/raw").rglob("*.csv"))
    assert not list((root / "data/raw").rglob("*.part"))
    assert not store.manifest["files"]


@pytest.mark.parametrize(
    "response",
    [
        Response(b"body", status=403),
        Response(b"short", length=100),
        Response(b"<html>error</html>"),
        Response(b""),
    ],
)
def test_reject_response_before_final_file(root, monkeypatch, response):
    store = get_store(root)
    monkeypatch.setattr("ossgeo.storage.open_https", lambda *a, **k: response)
    with pytest.raises(DataError):
        store.fetch("test", "bad", "https://example.org/bad", "bad.csv", "csv", "terms")
    assert not list((root / "data/raw").rglob("bad.csv"))


def test_cache_tampering_missing_restore_and_changed_bytes(remote, monkeypatch):
    store, calls = remote
    fetch_all(store, "core")
    record = store.manifest["files"]["github:developers"]
    path = store.root / record["path"]
    original = path.read_bytes()
    path.write_bytes(original.replace(b"123", b"124"))  # same size, different digest
    with pytest.raises(DataError, match="corrompu"):
        fetch_all(store, "core")
    path.unlink()
    fetch_all(store, "core")
    assert path.read_bytes() == original
    path.unlink()
    monkeypatch.setattr(
        "ossgeo.storage.open_https",
        lambda request, **k: Response(
            original.replace(b"123", b"125"), request.full_url
        ),
    )
    with pytest.raises(DataError, match="Octets différents"):
        fetch_all(store, "core")
    assert not path.exists()
    with pytest.raises(DataError, match="absent"):
        store.verify(record)


def test_pins_profiles_and_deliberate_update(remote):
    store, calls = remote
    fetch_all(store, "core")
    revisions = store.manifest["revisions"].copy()
    fetch_all(store, "all")
    assert store.manifest["completed_profiles"] == ["all", "core"]
    assert revisions == store.manifest["revisions"]
    assert sum("/commits/" in url for url in calls) == 2
    count = len(calls)
    fetch_all(store, "all")
    assert count == len(calls)
    assert existing_store(store.root).manifest["snapshot"] == store.manifest["snapshot"]
    new = get_store(store.root, update=True)
    assert new.manifest["snapshot"] != store.manifest["snapshot"]
    assert store.path.exists()
    for record in store.manifest["files"].values():
        store.verify(record)
    (store.root / "config/sources.toml").write_text(
        "# changed\n" + (store.root / "config/sources.toml").read_text()
    )
    with pytest.raises(DataError, match="Configuration"):
        get_store(store.root)


def test_cached_revision_response_is_verified_and_restored(remote):
    store, calls = remote
    fetch_all(store, "core")
    record = store.manifest["files"]["github:revision"]
    path = store.root / record["path"]
    original = path.read_bytes()
    path.write_bytes(original.replace(b"a", b"b"))
    with pytest.raises(DataError, match="corrompu"):
        fetch_all(store, "core")
    path.unlink()
    count = len(calls)
    fetch_all(store, "core")
    assert len(calls) == count + 1
    assert path.read_bytes() == original


def test_orphan_changed_url_and_non_https(root, monkeypatch):
    store = get_store(root)
    path = store.root / "data/raw/test" / store.manifest["snapshot"] / "file.txt"
    atomic_bytes(path, b"SYNTHETIC orphan")
    with pytest.raises(DataError, match="non répertorié"):
        store.fetch(
            "test", "file", "https://example.org/file", "file.txt", "text", "terms"
        )
    with pytest.raises(DataError, match="non HTTPS"):
        store.fetch(
            "test", "file", "http://example.org/file", "file.txt", "text", "terms"
        )
    with pytest.raises(DataError, match="non HTTPS"):
        HttpsRedirect().redirect_request(None, None, 302, "", {}, "http://example.org")
    path.unlink()
    monkeypatch.setattr(
        "ossgeo.storage.open_https",
        lambda req, **k: Response(b"SYNTHETIC", req.full_url),
    )
    store.fetch("test", "file", "https://example.org/file", "file.txt", "text", "terms")
    with pytest.raises(DataError, match="Source modifiée"):
        store.fetch(
            "test", "file", "https://example.org/changed", "file.txt", "text", "terms"
        )


def test_api_errors_and_invalid_revision(root, monkeypatch):
    store = get_store(root)

    def error(*a, **k):
        raise urllib.error.HTTPError(
            "https://example.org", 404, "SYNTHETIC not found", {}, None
        )

    monkeypatch.setattr("ossgeo.storage.open_https", error)
    with pytest.raises(DataError, match="404"):
        resolve_revision(store, "github", store.manifest["config"]["github"])
    monkeypatch.setattr(
        "ossgeo.storage.open_https",
        lambda req, **k: Response(b'{"sha":"short"}', req.full_url),
    )
    with pytest.raises(DataError, match="SHA Git complet"):
        resolve_revision(store, "github", store.manifest["config"]["github"])


@pytest.mark.parametrize(
    "kind,body",
    [
        ("json", b"invalid"),
        ("geojson", b"[]"),
        ("csv", b"error"),
        ("text", b"<!DOCTYPE html>"),
    ],
)
def test_payload_contract(root, kind, body):
    path = root / "SYNTHETIC"
    path.write_bytes(body)
    with pytest.raises((DataError, ValueError)):
        check_payload(path, kind)


def test_atomic_manifest_provenance(remote):
    store, _ = remote
    fetch_all(store, "core")
    saved = read_json(store.path)
    for record in saved["files"].values():
        assert record["requested_url"].startswith("https://")
        assert record["final_url"].startswith("https://")
        assert record["retrieved_at"].endswith("+00:00")
        assert record["terms"]
        assert sha256(store.root / record["path"]) == record["sha256"]
        assert record["revision"] or record["api_metadata"]
    assert not list(store.root.rglob("*.part"))

"""SYNTHETIC fixtures only: tiny invented observations, never research data."""

import csv
import io
import json
import shutil
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from ossgeo.acquire import get_store
from ossgeo.validate import DIMENSIONS, METRICS

PROJECT = Path(__file__).resolve().parents[1]
SHA = "a" * 40


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline tests must not contact the network")

    monkeypatch.setattr("ossgeo.storage.open_https", forbidden)
    monkeypatch.setattr("socket.create_connection", forbidden)


@pytest.fixture
def root(tmp_path):
    (tmp_path / "config").mkdir()
    for name in ("sources.toml", "geography_overrides.csv"):
        shutil.copyfile(PROJECT / "config" / name, tmp_path / "config" / name)
    return tmp_path


@pytest.fixture
def economies():
    return [
        {
            "id": "FRA",
            "iso2Code": "FR",
            "name": "SYNTHETIC France",
            "region": {"id": "ECS"},
        },
        {
            "id": "USA",
            "iso2Code": "US",
            "name": "SYNTHETIC USA",
            "region": {"id": "NAC"},
        },
        {
            "id": "WLD",
            "iso2Code": "1W",
            "name": "SYNTHETIC aggregate",
            "region": {"id": "NA"},
        },
    ]


def observation(code="FRA", code2="FR", year="2020", value=123):
    return {
        "countryiso3code": code,
        "country": {"id": code2},
        "date": year,
        "value": value,
        "indicator": {"id": "SP.POP.TOTL"},
    }


def feature(code="FR", eh="FR", adm="FRA"):
    return {
        "type": "Feature",
        "properties": {"ISO_A2": code, "ISO_A2_EH": eh, "ADM0_A3": adm},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
        },
    }


def table(name):
    fields = ["year", "quarter", *DIMENSIONS[name]]
    if name == "languages":
        fields.append("language_type")
    fields.append(METRICS[name])
    rows = []
    for year in (2020, 2025, 2026):
        row = {field: "SYNTHETIC" for field in fields}
        row.update(year=str(year), quarter="1")
        row[METRICS[name]] = "123"
        for field in ("iso2_code", "source", "destination"):
            if field in row:
                row[field] = "FR" if field != "destination" else "ZZ"
        rows.append(row)
    schema = {
        "fields": [
            {
                "name": f,
                "type": (
                    "integer" if f in {"year", "quarter", METRICS[name]} else "string"
                ),
            }
            for f in fields
        ]
    }
    return fields, rows, schema


class Response(io.BytesIO):
    def __init__(
        self, body, url="https://example.org/synthetic", status=200, length=None
    ):
        super().__init__(body)
        self.url = url
        self.status = status
        self.headers = {"Content-Length": str(len(body) if length is None else length)}

    def geturl(self):
        return self.url


@pytest.fixture
def remote(root, economies, monkeypatch):
    """Serve a complete synthetic provider universe through mocked HTTPS."""
    resources, files = [], {}
    for name in DIMENSIONS:
        fields, rows, schema = table(name)
        path = (
            ("representativeness_data/" if name.startswith("distinct_") else "data/")
            + name
            + ".csv"
        )
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        files[path] = stream.getvalue().encode()
        resources.append(
            {"name": name, "path": "data/" + name + ".csv", "schema": schema}
        )
    files["datapackage.json"] = json.dumps({"resources": resources}).encode()
    calls = []

    def opener(request, *, timeout):
        url = request.full_url
        calls.append(url)
        parsed = urlsplit(url)
        if parsed.hostname == "api.github.com":
            body = (
                {"sha": SHA}
                if "/commits/" in url
                else {
                    "truncated": False,
                    "tree": [{"path": path, "type": "blob"} for path in files],
                }
            )
            return Response(json.dumps(body).encode(), url)
        if parsed.hostname == "api.worldbank.org":
            params = parse_qs(parsed.query)
            page, per_page = int(params["page"][0]), int(params["per_page"][0])
            if "/country/all/" in url:
                rows = [
                    observation(),
                    observation(year="2025", value=None),
                    observation("WLD", "1W", value=999),
                ]
            elif "/indicator/" in url:
                rows = [{"id": "SP.POP.TOTL", "sourceNote": "SYNTHETIC"}]
            else:
                rows = economies
            header = {
                "page": page,
                "pages": (len(rows) + per_page - 1) // per_page,
                "per_page": str(per_page),
                "total": len(rows),
                "lastupdated": "2026-01-01",
            }
            body = [header, rows[(page - 1) * per_page : page * per_page]]
            return Response(json.dumps(body).encode(), url)
        path = parsed.path.split("/" + SHA + "/", 1)[1]
        if path.endswith(".geojson"):
            body = json.dumps(
                {"type": "FeatureCollection", "features": [feature("-99")]}
            ).encode()
        else:
            body = files.get(path, b"SYNTHETIC support file\n")
        return Response(body, url)

    monkeypatch.setattr("ossgeo.storage.open_https", opener)
    return get_store(root), calls

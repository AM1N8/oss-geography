"""Harmonise observations and emit explicit coverage/audit tables."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

from ossgeo.geography import is_aggregate
from ossgeo.storage import (
    DataError,
    Json,
    Store,
    atomic_bytes,
    atomic_json,
    sha256,
    utc_now,
)
from ossgeo.validate import validate


def write_csv(path: Path, fields: list[str], rows: list[Json]) -> None:
    """Serialize None as an empty cell, retaining missing values without zero-fill."""
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    atomic_bytes(path, stream.getvalue().encode("utf-8"))


def population_tables(
    economies: list[Json], observations: list[Json], start: int, end: int
) -> tuple[list[Json], list[Json], list[Json]]:
    """Separate aggregates and distinguish API nulls from absent observations."""
    economy_by_iso2 = {e["iso2Code"]: e for e in economies}
    population, excluded, coverage = [], [], []
    observed: dict[tuple[str, int], Json] = {}
    for observation in observations:
        economy = economy_by_iso2[observation["country"]["id"]]
        row = {
            "wb_iso3": economy["id"],
            "wb_iso2": economy["iso2Code"],
            "year": int(observation["date"]),
            "population": observation["value"],
        }
        if is_aggregate(economy):
            excluded.append(
                {**row, "name": economy["name"], "reason": "WB_region_NA_aggregate"}
            )
        else:
            population.append(row)
            observed[(row["wb_iso3"], row["year"])] = row
    for economy in economies:
        if is_aggregate(economy):
            continue
        for year in range(start, end + 1):
            observation_row = observed.get((economy["id"], year))
            status = (
                "absent_observation"
                if observation_row is None
                else (
                    "missing_value"
                    if observation_row["population"] is None
                    else "observed"
                )
            )
            coverage.append({"wb_iso3": economy["id"], "year": year, "status": status})
    return (
        sorted(population, key=lambda r: (r["wb_iso3"], r["year"])),
        excluded,
        coverage,
    )


def prepare(store: Store) -> Path:
    """Validate first, then write tables under a content-addressed preparation ID."""
    report, inputs = validate(store)
    if report["errors"] or inputs is None:
        raise DataError(
            f"Préparation bloquée par {len(report['errors'])} erreur(s) ; consulter data/metadata/quality/"
        )
    overrides = store.root / "config/geography_overrides.csv"
    # Include code, overrides and input digests: changed preparation never replaces an old run.
    code_hashes = {
        p.name: sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))
    }
    provenance = {
        "snapshot": store.manifest["snapshot"],
        "code_sha256": code_hashes,
        "overrides_sha256": sha256(overrides),
        "inputs_sha256": {k: v["sha256"] for k, v in store.manifest["files"].items()},
    }
    preparation_id = hashlib.sha256(
        json.dumps(provenance, sort_keys=True).encode()
    ).hexdigest()[:16]
    output = (
        store.root / "data/processed" / str(store.manifest["snapshot"]) / preparation_id
    )
    marker = store.root / "data/metadata/preparations" / f"{preparation_id}.json"
    if marker.exists():
        from ossgeo.storage import read_json

        previous = read_json(marker)
        for name, digest in previous["outputs_sha256"].items():
            if not (output / name).is_file() or sha256(output / name) != digest:
                raise DataError(f"Sortie préparée absente/corrompue : {output / name}")
        return output
    if output.exists() and any(output.iterdir()):
        raise DataError(
            f"Préparation incomplète existante : conserver/renommer {output} puis relancer"
        )
    output.mkdir(parents=True, exist_ok=True)
    study = store.manifest["config"]["study"]
    start, end = study["start_year"], study["end_year"]
    mappings = {row["github_code"]: row for row in inputs["correspondences"]}
    coverage = []
    for name, table in inputs["tables"].items():
        prepared = []
        fields = [
            (
                "developer_accounts"
                if f == "developers"
                else "github_code" if f == "iso2_code" else f
            )
            for f in table["fields"]
        ]
        geography_fields = [
            f for f in ("iso2_code", "source", "destination") if f in table["fields"]
        ]
        for field in geography_fields:
            prefix = "" if field == "iso2_code" else field + "_"
            fields.extend([prefix + "wb_iso3", prefix + "ne_adm0_a3"])
        per_economy: Counter[tuple[str, int, int]] = Counter()
        for row in table["rows"]:
            year, quarter = int(row["year"]), int(row["quarter"])
            if not start <= year <= end:
                continue
            clean = {
                (
                    "developer_accounts"
                    if k == "developers"
                    else "github_code" if k == "iso2_code" else k
                ): v
                for k, v in row.items()
            }
            for field in geography_fields:
                match = mappings[row[field]]
                prefix = "" if field == "iso2_code" else field + "_"
                clean[prefix + "wb_iso3"] = match["wb_iso3"]
                clean[prefix + "ne_adm0_a3"] = match["ne_adm0_a3"]
            prepared.append(clean)
            codes = {row[f] for f in geography_fields} or {""}
            for code in codes:
                per_economy[(code, year, quarter)] += 1
        write_csv(output / f"{name}.csv", fields, prepared)
        table_codes = sorted({code for code, _, _ in per_economy}) or [""]
        for code in table_codes:
            for year in range(start, end + 1):
                for quarter in range(1, 5):
                    count = per_economy[(code, year, quarter)]
                    coverage.append(
                        {
                            "table": name,
                            "github_code": code,
                            "year": year,
                            "quarter": quarter,
                            "published_rows": count,
                            "status": "published" if count else "absent_observation",
                        }
                    )
    population, excluded, population_coverage = population_tables(
        inputs["economies"], inputs["population"], start, end
    )
    write_csv(
        output / "population.csv",
        ["wb_iso3", "wb_iso2", "year", "population"],
        population,
    )
    write_csv(
        output / "population_coverage.csv",
        ["wb_iso3", "year", "status"],
        population_coverage,
    )
    write_csv(
        output / "excluded_wb_aggregates.csv",
        ["wb_iso3", "wb_iso2", "year", "population", "name", "reason"],
        excluded,
    )
    write_csv(
        output / "geographic_correspondences.csv",
        [
            "github_code",
            "wb_iso3",
            "wb_iso2",
            "ne_adm0_a3",
            "ne_iso_a2",
            "ne_iso_a2_eh",
            "wb_method",
            "ne_method",
        ],
        inputs["correspondences"],
    )
    write_csv(
        output / "unmatched_github_codes.csv",
        ["github_code", "target", "reason"],
        inputs["unmatched"],
    )
    write_csv(
        output / "github_coverage.csv",
        ["table", "github_code", "year", "quarter", "published_rows", "status"],
        coverage,
    )
    atomic_json(
        marker,
        {
            **provenance,
            "preparation_id": preparation_id,
            "prepared_at": utc_now(),
            "output_path": str(output.relative_to(store.root)),
            "outputs_sha256": {p.name: sha256(p) for p in sorted(output.glob("*.csv"))},
            "population_coverage": dict(
                Counter(r["status"] for r in population_coverage)
            ),
            "warnings": report["warnings"],
        },
    )
    return output

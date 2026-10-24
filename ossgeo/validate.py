"""Offline data contracts and coverage diagnostics, without research statistics."""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path
from typing import Any

from ossgeo.acquire import wb_rows
from ossgeo.geography import correspondences, is_aggregate, valid_iso2
from ossgeo.storage import DataError, Json, Store, atomic_json, read_json, utc_now

# Natural observation keys: a language's type is an attribute, not a second language.
DIMENSIONS = {
    "developers": ["iso2_code"],
    "git_pushes": ["iso2_code"],
    "economy_collaborators": ["source", "destination"],
    "languages": ["iso2_code", "language"],
    "licenses": ["iso2_code", "spdx_license"],
    "topics": ["iso2_code", "topic"],
    "repositories": ["iso2_code"],
    "organizations": ["iso2_code"],
    "distinct_dataset_counts_by_quarter_by_economy": ["iso2_code"],
    "distinct_economy_counts_by_quarter_by_dataset": ["dataset"],
}
METRICS = {
    "developers": "developers",
    "git_pushes": "git_pushes",
    "economy_collaborators": "weight",
    "languages": "num_pushers",
    "licenses": "num_pushers",
    "topics": "num_pushers",
    "repositories": "repositories",
    "organizations": "organizations",
    "distinct_dataset_counts_by_quarter_by_economy": "count_of_datasets",
    "distinct_economy_counts_by_quarter_by_dataset": "count_distinct_economies",
}


def csv_rows(path: Path) -> tuple[list[str], list[Json]]:
    """Read a CSV while detecting malformed row widths and duplicate headers."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        if len(fields) != len(set(fields)):
            raise DataError(f"En-têtes dupliqués : {path.name}")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise DataError(f"Largeur de ligne incorrecte : {path.name}")
    return fields, rows


def validate_table(
    name: str, fields: list[str], rows: list[Json], schema: Json
) -> Json:
    """Validate schema types, nonnegative counts, periods and natural keys."""
    errors: list[str] = []
    warnings: list[str] = []
    required = {f["name"]: f["type"] for f in schema["fields"]}
    contract = {*DIMENSIONS[name], METRICS[name], "year", "quarter"}
    if name == "languages":
        contract.add("language_type")
    expected_types = {
        field: "integer" if field in {"year", "quarter", METRICS[name]} else "string"
        for field in contract
    }
    if (
        not contract <= required.keys()
        or not required.keys() <= set(fields)
        or any(required.get(field) != kind for field, kind in expected_types.items())
    ):
        return {
            "errors": [f"{name} : colonnes requises absentes ou schéma inattendu"],
            "warnings": [],
            "rows": len(rows),
            "periods": [],
            "economies": [],
        }
    seen: set[tuple[str, ...]] = set()
    periods, codes = set(), set()
    missing_count = 0
    for number, row in enumerate(rows, 2):
        key = tuple(row[field] for field in ["year", "quarter", *DIMENSIONS[name]])
        if key in seen:
            errors.append(f"{name}:{number} : clé dupliquée {key}")
        seen.add(key)
        for field, kind in required.items():
            value = row[field]
            if value == "" and field == METRICS[name]:
                missing_count += 1
                continue
            if kind == "integer":
                if not re.fullmatch(r"-?\d+", value):
                    errors.append(f"{name}:{number} : entier attendu pour {field}")
                    continue
                integer = int(value)
                if (
                    integer < 0
                    or (field == "year" and not 1900 <= integer <= 2100)
                    or (field == "quarter" and not 1 <= integer <= 4)
                ):
                    errors.append(f"{name}:{number} : valeur invalide {field}={value}")
            elif kind != "string" or not value:
                errors.append(f"{name}:{number} : chaîne requise pour {field}")
        for field in ("iso2_code", "source", "destination"):
            if field in row:
                codes.add(row[field])
                if not valid_iso2(row[field]):
                    errors.append(
                        f"{name}:{number} : code géographique invalide {row[field]!r}"
                    )
        periods.add(f"{row['year']}-Q{row['quarter']}")
    if missing_count:
        warnings.append(f"{name} : {missing_count} mesures manquantes, conservées")
    if not rows:
        warnings.append(f"{name} : aucune observation publiée")
    return {
        "errors": errors,
        "warnings": warnings,
        "rows": len(rows),
        "periods": sorted(periods),
        "economies": sorted(codes),
    }


def validate_world_bank(
    economies: list[Json],
    population: list[Json],
    indicator: list[Json],
    start: int,
    end: int,
) -> Json:
    """Check population keys/types without requiring complete coverage."""
    errors, warnings = [], []
    ids, iso2 = set(), set()
    for economy in economies:
        if (
            not {"id", "iso2Code", "name", "region"} <= economy.keys()
            or not all(
                isinstance(economy.get(field), str) and economy[field]
                for field in ("id", "iso2Code", "name")
            )
            or not isinstance(economy.get("region"), dict)
            or not isinstance(economy["region"].get("id"), str)
            or not economy["region"]["id"]
        ):
            errors.append("World Bank : métadonnées d'économie incomplètes")
            continue
        if economy["id"] in ids or economy["iso2Code"] in iso2:
            errors.append(f"World Bank : économie dupliquée {economy['id']}")
        ids.add(economy["id"])
        iso2.add(economy["iso2Code"])
    if len(indicator) != 1 or indicator[0].get("id") != "SP.POP.TOTL":
        errors.append("World Bank : métadonnées de l'indicateur incorrectes")
    seen = set()
    missing = 0
    economy_by_iso2 = {e["iso2Code"]: e for e in economies if "iso2Code" in e}
    empty_iso3: set[str] = set()
    for row in population:
        if (
            not {"countryiso3code", "country", "indicator", "date", "value"}
            <= row.keys()
            or not isinstance(row.get("country"), dict)
            or not isinstance(row.get("indicator"), dict)
            or not isinstance(row.get("countryiso3code"), str)
        ):
            errors.append("World Bank : observation de population incomplète")
            continue
        code = row["countryiso3code"]
        code2 = row["country"].get("id")
        key = (code2, row["date"])
        if key in seen:
            errors.append(f"World Bank : clé dupliquée {key}")
        seen.add(key)
        if (
            not isinstance(row["date"], str)
            or not re.fullmatch(r"\d{4}", row["date"])
            or not start <= int(row["date"]) <= end
        ):
            errors.append(f"World Bank : année invalide {row['date']}")
        matched_economy = economy_by_iso2.get(code2)
        if not matched_economy or (code and code != matched_economy["id"]):
            errors.append(f"World Bank : identifiants incohérents {code}")
        if not code and matched_economy:
            empty_iso3.add(str(code2))
        if row["indicator"].get("id") != "SP.POP.TOTL":
            errors.append("World Bank : indicateur inattendu")
        value = row["value"]
        if value is None:
            missing += 1
        elif (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            errors.append(f"World Bank : population invalide {key}")
    if missing:
        warnings.append(
            f"World Bank : {missing} valeurs de population nulles (agrégats compris)"
        )
    if empty_iso3:
        warnings.append(
            f"World Bank : ISO3 vide pour {', '.join(sorted(empty_iso3))} ; identifiant country.id relié exactement à iso2Code des métadonnées"
        )
    return {
        "errors": errors,
        "warnings": warnings,
        "rows": len(population),
        "years": sorted({str(row.get("date", "")) for row in population}),
    }


def validate_geojson(value: Any) -> Json:
    """Check country polygons, stable IDs and coordinate structure, not topology."""
    errors, warnings = [], []
    if (
        not isinstance(value, dict)
        or value.get("type") != "FeatureCollection"
        or not isinstance(value.get("features"), list)
        or not value["features"]
    ):
        return {
            "errors": ["Natural Earth : FeatureCollection vide ou invalide"],
            "warnings": [],
        }
    seen: set[str] = set()
    invalid: list[str] = []
    for feature in value["features"]:
        if not isinstance(feature, dict):
            errors.append("Natural Earth : objet Feature attendu")
            continue
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if (
            feature.get("type") != "Feature"
            or not isinstance(properties, dict)
            or not {"ISO_A2", "ISO_A2_EH", "ADM0_A3"} <= properties.keys()
        ):
            errors.append("Natural Earth : attributs/Feature requis absents")
            continue
        identifier = properties["ADM0_A3"]
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier == "-99"
            or identifier in seen
        ):
            errors.append(f"Natural Earth : ADM0_A3 absent/dupliqué {identifier}")
        seen.add(identifier)
        if not valid_iso2(properties["ISO_A2"]) or not valid_iso2(
            properties["ISO_A2_EH"]
        ):
            invalid.append(identifier)
        if not isinstance(geometry, dict) or geometry.get("type") not in {
            "Polygon",
            "MultiPolygon",
        }:
            errors.append(f"Natural Earth : géométrie invalide {identifier}")
            continue
        coordinates = geometry.get("coordinates", [])
        polygons = [coordinates] if geometry["type"] == "Polygon" else coordinates
        try:
            if not polygons:
                raise ValueError("empty")
            for polygon in polygons:
                if not polygon:
                    raise ValueError("empty")
                for ring in polygon:
                    if len(ring) < 4 or ring[0] != ring[-1]:
                        raise ValueError("ring")
                    for point in ring:
                        if (
                            len(point) < 2
                            or not all(
                                isinstance(n, (int, float))
                                and not isinstance(n, bool)
                                and math.isfinite(n)
                                for n in point
                            )
                            or not -180 <= point[0] <= 180
                            or not -90 <= point[1] <= 90
                        ):
                            raise ValueError("position")
        except (TypeError, ValueError, IndexError):
            errors.append(f"Natural Earth : coordonnées invalides {identifier}")
    if invalid:
        warnings.append(
            f"Natural Earth : ISO_A2/ISO_A2_EH incomplets pour {', '.join(sorted(invalid))}"
        )
    return {
        "errors": errors,
        "warnings": warnings,
        "features": len(value["features"]),
        "incomplete_identifiers": sorted(invalid),
    }


def load_inputs(store: Store) -> Json:
    """Load only files described by the active manifest."""
    records = store.manifest["files"]
    schema = read_json(store.root / records["github:datapackage.json"]["path"])
    resources = {item["name"]: item for item in schema["resources"]}
    tables = {}
    for name in DIMENSIONS:
        record = records.get(f"github:{name}")
        if record:
            fields, rows = csv_rows(store.root / record["path"])
            tables[name] = {
                "fields": fields,
                "rows": rows,
                "schema": resources[name]["schema"],
            }
    ne_path = store.manifest["config"]["natural_earth"]["path"]
    return {
        "tables": tables,
        "economies": wb_rows(store, "economies"),
        "population": wb_rows(store, "population"),
        "indicator": wb_rows(store, "indicator"),
        "geojson": read_json(store.root / records[f"natural_earth:{ne_path}"]["path"]),
    }


def validate(store: Store) -> tuple[Json, Json | None]:
    """Produce a quality report; genuine errors block downstream preparation."""
    report: Json = {
        "snapshot": store.manifest["snapshot"],
        "validated_at": utc_now(),
        "errors": [],
        "warnings": [],
        "tables": {},
    }
    inputs = None
    try:
        if "core" not in store.manifest["completed_profiles"]:
            raise DataError(
                "Acquisition CORE incomplète : reprendre fetch --profile core"
            )
        for record in store.manifest["files"].values():
            store.verify(record)
        inputs = load_inputs(store)
        study = store.manifest["config"]["study"]
        codes: set[str] = set()
        for name, table in inputs["tables"].items():
            result = validate_table(
                name, table["fields"], table["rows"], table["schema"]
            )
            report["tables"][name] = result
            codes.update(result["economies"])
            periods = set(result["periods"])
            missing_periods = [
                f"{year}-Q{quarter}"
                for year in range(study["start_year"], study["end_year"] + 1)
                for quarter in range(1, 5)
                if f"{year}-Q{quarter}" not in periods
            ]
            result["missing_study_periods"] = missing_periods
            if missing_periods:
                result["warnings"].append(
                    f"{name} : trimestres non publiés {', '.join(missing_periods)}"
                )
        report["tables"]["world_bank"] = validate_world_bank(
            inputs["economies"],
            inputs["population"],
            inputs["indicator"],
            study["start_year"],
            study["end_year"],
        )
        report["tables"]["natural_earth"] = validate_geojson(inputs["geojson"])
        for result in report["tables"].values():
            report["errors"].extend(result["errors"])
            report["warnings"].extend(result["warnings"])
        if not report["errors"]:
            matches, unmatched = correspondences(
                codes,
                inputs["economies"],
                inputs["geojson"]["features"],
                store.root / "config/geography_overrides.csv",
            )
            inputs["correspondences"], inputs["unmatched"] = matches, unmatched
            report["unmatched_codes"] = unmatched
            if unmatched:
                report["warnings"].append(
                    f"Géographie : {len(unmatched)} correspondances absentes/ambiguës, voir unmatched_codes"
                )
            observed = {
                (r["country"]["id"], int(r["date"])) for r in inputs["population"]
            }
            absent = sum(
                (e["iso2Code"], y) not in observed
                for e in inputs["economies"]
                if not is_aggregate(e)
                for y in range(study["start_year"], study["end_year"] + 1)
            )
            if absent:
                report["warnings"].append(
                    f"World Bank : {absent} couples économie-année non publiés"
                )
    except (DataError, OSError, ValueError, KeyError, TypeError) as error:
        report["errors"].append(str(error))
    report["error_count"] = len(report["errors"])
    report["warning_count"] = len(report["warnings"])
    atomic_json(
        store.root / "data/metadata/quality" / f"{store.manifest['snapshot']}.json",
        report,
    )
    return report, inputs

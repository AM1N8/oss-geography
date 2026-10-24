"""Conservative identifier-based correspondences, never name-based joins."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from ossgeo.storage import DataError, Json


def valid_iso2(value: object) -> bool:
    """Accept an explicit two-letter identifier, excluding Natural Earth -99."""
    return isinstance(value, str) and re.fullmatch(r"[A-Z]{2}", value) is not None


def is_aggregate(economy: Json) -> bool:
    """Use the World Bank region marker, not code lengths or country names."""
    return bool(economy["region"]["id"] == "NA")


def correspondences(
    codes: set[str], economies: list[Json], features: list[Json], overrides_path: Path
) -> tuple[list[Json], list[Json]]:
    """Match exact ISO2 codes, using ISO_A2_EH only when ISO_A2 is unavailable.

    Multiple candidates remain unmatched. Reviewed explicit overrides may use
    World Bank ISO3 IDs and Natural Earth ADM0_A3, with mandatory provenance.
    """
    wb: dict[str, list[Json]] = {}
    ne: dict[str, list[Json]] = {}
    individual = [row for row in economies if not is_aggregate(row)]
    for economy in individual:
        wb.setdefault(economy["iso2Code"], []).append(economy)
    for feature in features:
        properties = feature["properties"]
        field = "ISO_A2" if valid_iso2(properties.get("ISO_A2")) else "ISO_A2_EH"
        if valid_iso2(properties.get(field)):
            ne.setdefault(properties[field], []).append(properties)
    overrides: dict[str, Json] = {}
    with overrides_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "github_code",
            "wb_iso3",
            "ne_adm0_a3",
            "reviewed_by",
            "reviewed_on",
            "reason",
            "source_url",
        }
        if set(reader.fieldnames or []) != required:
            raise DataError("En-tête incorrect : config/geography_overrides.csv")
        for row in reader:
            code = row["github_code"]
            if (
                code in overrides
                or not valid_iso2(code)
                or not all(
                    row[field]
                    for field in ("reviewed_by", "reviewed_on", "reason", "source_url")
                )
                or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["reviewed_on"])
                or not row["source_url"].startswith("https://")
                or not (row["wb_iso3"] or row["ne_adm0_a3"])
            ):
                raise DataError(
                    f"Override non documenté, invalide ou dupliqué : {code}"
                )
            overrides[code] = row
    result, unmatched = [], []
    for code in sorted(codes):
        wb_candidates, ne_candidates = wb.get(code, []), ne.get(code, [])
        wb_method, ne_method = "iso2_exact", "ISO_A2"
        override = overrides.get(code, {})
        if override.get("wb_iso3"):
            wb_candidates = [e for e in individual if e["id"] == override["wb_iso3"]]
            wb_method = "reviewed_override"
            if len(wb_candidates) != 1:
                raise DataError(f"Cible World Bank invalide dans l'override : {code}")
        if override.get("ne_adm0_a3"):
            ne_candidates = [
                f["properties"]
                for f in features
                if f["properties"]["ADM0_A3"] == override["ne_adm0_a3"]
            ]
            ne_method = "reviewed_override"
            if len(ne_candidates) != 1:
                raise DataError(
                    f"Cible Natural Earth invalide dans l'override : {code}"
                )
        wb_match = wb_candidates[0] if len(wb_candidates) == 1 else {}
        ne_match = ne_candidates[0] if len(ne_candidates) == 1 else {}
        if (
            ne_match
            and ne_method != "reviewed_override"
            and not valid_iso2(ne_match["ISO_A2"])
        ):
            ne_method = "ISO_A2_EH_fallback"
        row = {
            "github_code": code,
            "wb_iso3": wb_match.get("id", ""),
            "wb_iso2": wb_match.get("iso2Code", ""),
            "ne_adm0_a3": ne_match.get("ADM0_A3", ""),
            "ne_iso_a2": ne_match.get("ISO_A2", ""),
            "ne_iso_a2_eh": ne_match.get("ISO_A2_EH", ""),
            "wb_method": wb_method if wb_match else "unmatched",
            "ne_method": ne_method if ne_match else "unmatched",
        }
        result.append(row)
        for target, candidates in (
            ("world_bank", wb_candidates),
            ("natural_earth", ne_candidates),
        ):
            if len(candidates) != 1:
                unmatched.append(
                    {
                        "github_code": code,
                        "target": target,
                        "reason": "ambiguous" if candidates else "no_code_match",
                    }
                )
    # Validate unused overrides too: they may reappear in a later publication.
    for code, override in overrides.items():
        if override["wb_iso3"] and override["wb_iso3"] not in {
            e["id"] for e in individual
        }:
            raise DataError(f"Cible World Bank invalide dans l'override : {code}")
        if override["ne_adm0_a3"] and override["ne_adm0_a3"] not in {
            f["properties"]["ADM0_A3"] for f in features
        }:
            raise DataError(f"Cible Natural Earth invalide dans l'override : {code}")
    return result, unmatched

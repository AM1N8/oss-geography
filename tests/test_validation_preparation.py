"""SYNTHETIC observations: keys, nulls, geography and end-to-end auditability."""

import pytest

from conftest import feature, observation, table
from ossgeo.acquire import fetch_all
from ossgeo.cli import main
from ossgeo.geography import correspondences, is_aggregate
from ossgeo.prepare import population_tables, prepare
from ossgeo.storage import DataError
from ossgeo.validate import (
    DIMENSIONS,
    csv_rows,
    validate,
    validate_geojson,
    validate_table,
    validate_world_bank,
)


@pytest.mark.parametrize("name", DIMENSIONS)
def test_table_specific_duplicates(name):
    fields, rows, schema = table(name)
    assert not validate_table(name, fields, rows, schema)["errors"]
    duplicate = dict(rows[0])
    if name == "languages":
        duplicate["language_type"] = "SYNTHETIC different attribute, same key"
    result = validate_table(name, fields, rows + [duplicate], schema)
    assert any("dupliquée" in e for e in result["errors"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("developers", "-1"),
        ("developers", "NaN"),
        ("quarter", "5"),
        ("year", "0"),
        ("iso2_code", "fra"),
        ("iso2_code", ""),
    ],
)
def test_bad_counts_periods_and_codes(field, value):
    fields, rows, schema = table("developers")
    rows[0][field] = value
    assert validate_table("developers", fields, rows, schema)["errors"]


def test_missing_counts_schema_and_empty_tables():
    fields, rows, schema = table("developers")
    rows[0]["developers"] = ""
    result = validate_table("developers", fields, rows, schema)
    assert not result["errors"] and result["warnings"]
    assert validate_table("developers", fields[:-1], rows, schema)["errors"]
    assert validate_table("developers", fields, [], schema)["warnings"]
    fields, rows, schema = table("languages")
    schema["fields"][-1]["type"] = "object"
    assert validate_table("languages", fields, rows, schema)["errors"]


@pytest.mark.parametrize("text", ["a,a\n1,2\n", "a,b\n1\n", "a,b\n1,2,3\n"])
def test_malformed_csv(root, text):
    path = root / "SYNTHETIC.csv"
    path.write_text(text)
    with pytest.raises(DataError):
        csv_rows(path)


def test_missing_population_and_aggregate_exclusion(economies):
    observations = [observation(value=None), observation("WLD", "1W", value=999)]
    report = validate_world_bank(
        economies, observations, [{"id": "SP.POP.TOTL"}], 2020, 2025
    )
    assert not report["errors"] and report["warnings"]
    population, excluded, coverage = population_tables(
        economies, observations, 2020, 2025
    )
    assert population == [
        {"wb_iso3": "FRA", "wb_iso2": "FR", "year": 2020, "population": None}
    ]
    assert excluded[0]["wb_iso3"] == "WLD"
    assert is_aggregate(economies[2])
    assert {r["status"] for r in coverage} == {"missing_value", "absent_observation"}
    assert len(coverage) == 12


def test_empty_api_iso3_and_duplicates_use_country_id(economies):
    rows = [observation(code=""), observation(code="", code2="1W")]
    result = validate_world_bank(economies, rows, [{"id": "SP.POP.TOTL"}], 2020, 2025)
    assert not result["errors"] and result["warnings"]
    assert len(population_tables(economies, rows, 2020, 2025)[0]) == 1
    assert validate_world_bank(
        economies, rows + rows, [{"id": "SP.POP.TOTL"}], 2020, 2025
    )["errors"]


@pytest.mark.parametrize(
    "changes",
    [
        {"value": -1},
        {"value": True},
        {"value": float("inf")},
        {"value": "123"},
        {"date": "2030"},
        {"date": "bad"},
        {"countryiso3code": "XXX"},
        {"indicator": {"id": "bad"}},
        {"country": {"id": "ZZ"}},
        {"country": None},
        {"indicator": None},
        {"countryiso3code": None},
    ],
)
def test_population_errors(economies, changes):
    assert validate_world_bank(
        economies, [{**observation(), **changes}], [{"id": "SP.POP.TOTL"}], 2020, 2025
    )["errors"]


def test_invalid_economy_and_indicator_metadata(economies):
    result = validate_world_bank(economies + [economies[0], {}], [{}], [], 2020, 2025)
    assert len(result["errors"]) == 4


def test_geographic_matches_fallback_ambiguity_and_unmatched(root, economies):
    features = [feature("-99"), feature("US", "US", "USA")]
    matches, unmatched = correspondences(
        {"FR", "US", "ZZ"}, economies, features, root / "config/geography_overrides.csv"
    )
    by_code = {row["github_code"]: row for row in matches}
    assert by_code["FR"]["ne_method"] == "ISO_A2_EH_fallback"
    assert by_code["US"]["wb_iso3"] == "USA"
    assert by_code["ZZ"]["wb_iso3"] == ""
    assert len(unmatched) == 2
    features.append(feature("FR", "FR", "FXX"))
    _, unmatched = correspondences(
        {"FR"}, economies, features, root / "config/geography_overrides.csv"
    )
    assert unmatched == [
        {"github_code": "FR", "target": "natural_earth", "reason": "ambiguous"}
    ]


def test_reviewed_override_provenance_and_targets(root, economies):
    path = root / "config/geography_overrides.csv"
    header = path.read_text()
    path.write_text(
        header
        + "ZZ,FRA,FRA,group,2026-10-25,SYNTHETIC test,https://example.org/evidence\n"
    )
    matches, unmatched = correspondences({"ZZ"}, economies, [feature()], path)
    assert not unmatched and matches[0]["wb_method"] == "reviewed_override"
    assert matches[0]["ne_method"] == "reviewed_override"
    for row in [
        "ZZ,XXX,,group,2026-10-25,test,https://example.org\n",
        "ZZ,,XXX,group,2026-10-25,test,https://example.org\n",
        "ZZ,FRA,FRA,,,,\n",
    ]:
        path.write_text(header + row)
        with pytest.raises(DataError):
            correspondences({"ZZ"}, economies, [feature()], path)
    path.write_text(
        header + "ZZ,FRA,FRA,group,2026-10-25,test,https://example.org\n" * 2
    )
    with pytest.raises(DataError, match="dupliqué"):
        correspondences({"ZZ"}, economies, [feature()], path)
    path.write_text("bad header\n")
    with pytest.raises(DataError, match="En-tête"):
        correspondences(set(), economies, [], path)


@pytest.mark.parametrize(
    "change",
    [
        "empty",
        "properties",
        "duplicate",
        "geometry",
        "ring",
        "position",
        "polygon",
        "identifier",
        "feature_object",
    ],
)
def test_geojson_structure_and_identifiers(change):
    data = {"type": "FeatureCollection", "features": [feature()]}
    if change == "empty":
        data["features"] = []
    elif change == "feature_object":
        data["features"] = [None]
    elif change == "properties":
        data["features"][0]["properties"] = {}
    elif change == "duplicate":
        data["features"].append(feature())
    elif change == "geometry":
        data["features"][0]["geometry"]["type"] = "Point"
    elif change == "identifier":
        data["features"][0]["properties"]["ADM0_A3"] = "-99"
    elif change == "polygon":
        data["features"][0]["geometry"]["coordinates"] = []
    elif change == "ring":
        data["features"][0]["geometry"]["coordinates"][0].pop()
    else:
        data["features"][0]["geometry"]["coordinates"][0][1] = [181, 91]
    assert validate_geojson(data)["errors"]


def test_multipolygon_and_missing_iso_warnings():
    data = {"type": "FeatureCollection", "features": [feature("-99", "-99")]}
    geometry = data["features"][0]["geometry"]
    geometry["type"] = "MultiPolygon"
    geometry["coordinates"] = [geometry["coordinates"]]
    result = validate_geojson(data)
    assert not result["errors"] and result["warnings"]


def test_full_offline_pipeline_and_idempotence(remote):
    store, calls = remote
    fetch_all(store, "all")
    report, inputs = validate(store)
    assert not report["errors"]
    assert report["unmatched_codes"]
    assert "2020-Q2" in report["tables"]["developers"]["missing_study_periods"]
    output = prepare(store)
    assert (
        "2026"
        in (
            store.root / store.manifest["files"]["github:developers"]["path"]
        ).read_text()
    )
    fields, rows = csv_rows(output / "developers.csv")
    assert "developer_accounts" in fields and "developers" not in fields
    assert {r["year"] for r in rows} == {"2020", "2025"}
    assert (output / "languages.csv").exists()
    assert csv_rows(output / "population.csv")[1][1]["population"] == ""
    assert csv_rows(output / "economy_collaborators.csv")[1][0]["destination"] == "ZZ"
    assert csv_rows(output / "unmatched_github_codes.csv")[1]
    network_calls = len(calls)
    assert prepare(store) == output
    assert len(calls) == network_calls
    (output / "developers.csv").write_text("SYNTHETIC tampering")
    with pytest.raises(DataError, match="corrompue"):
        prepare(store)


def test_core_only_and_blocking_errors(remote):
    store, _ = remote
    report, _ = validate(store)
    assert report["errors"]
    with pytest.raises(DataError, match="bloquée"):
        prepare(store)
    fetch_all(store, "core")
    output = prepare(store)
    assert not (output / "languages.csv").exists()
    raw = store.root / store.manifest["files"]["github:developers"]["path"]
    raw.write_text("SYNTHETIC corruption")
    assert validate(store)[0]["errors"]


def test_cli_offline_commands(remote, capsys):
    store, _ = remote
    root_args = ["--root", str(store.root)]
    assert main(root_args + ["fetch", "--profile", "core"]) == 0
    assert main(root_args + ["status"]) == 0
    assert main(root_args + ["validate"]) == 0
    assert main(root_args + ["prepare"]) == 0
    store.manifest["completed_profiles"] = []
    store.save()
    assert main(root_args + ["validate"]) == 1
    assert "error_count" in capsys.readouterr().out


def test_cli_missing_snapshot_help_and_interrupt(root, monkeypatch, capsys):
    assert main(["--root", str(root), "status"]) == 1
    assert "Aucun instantané" in capsys.readouterr().err
    for flag in ("--help", "--version"):
        with pytest.raises(SystemExit) as exit_info:
            main([flag])
        assert exit_info.value.code == 0

    def interrupt(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr("ossgeo.cli.get_store", interrupt)
    assert main(["--root", str(root), "fetch"]) == 130

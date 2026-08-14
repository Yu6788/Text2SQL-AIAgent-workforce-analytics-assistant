from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from atlas_workforce.schema import TABLES  # noqa: E402
from build_database import build_database  # noqa: E402
from generate_data import generate_all, write_csvs  # noqa: E402
from validate_data import validate_frames  # noqa: E402


def test_generated_data_shapes_and_integrity() -> None:
    frames = generate_all()

    assert set(frames) == set(TABLES)
    assert len(frames["organizations"]) == 50
    assert len(frames["employees"]) == 5000
    assert len(frames["talent_reviews"]) == 15000
    assert len(frames["development_programs"]) == 40
    assert len(frames["employee_programs"]) == 8000
    assert len(frames["internal_moves"]) == 3000

    issues = validate_frames(frames)
    assert issues == []


def test_synthetic_business_patterns_are_observable() -> None:
    frames = generate_all()
    reviews = frames["talent_reviews"]
    completion = (
        reviews[reviews["review_status"] != "Cancelled"]
        .assign(completed=lambda df: df["review_status"].eq("Completed"))
        .groupby("review_cycle")["completed"]
        .mean()
    )
    assert completion["2026_H1"] > completion["2024_H1"]

    employees = frames["employees"]
    organizations = frames["organizations"]
    moves = frames["internal_moves"]
    emp_with_bu = employees.merge(
        organizations[["organization_id", "business_unit"]],
        on="organization_id",
        how="left",
    )
    promotions = moves[moves["move_type"] == "Promotion"].merge(
        emp_with_bu[["employee_id", "business_unit"]],
        on="employee_id",
        how="left",
    )
    active_counts = emp_with_bu.groupby("business_unit")["employee_id"].nunique()
    promo_counts = promotions.groupby("business_unit")["employee_id"].nunique()
    rates = (promo_counts / active_counts).fillna(0)

    assert rates["Technology"] > rates["Customer Experience"]


def test_duckdb_build_supports_core_query(tmp_path: Path) -> None:
    frames = generate_all()
    data_dir = tmp_path / "generated"
    db_path = tmp_path / "atlas_workforce.duckdb"
    write_csvs(frames, data_dir)
    build_database(data_dir, db_path)

    with duckdb.connect(str(db_path), read_only=True) as con:
        result = con.execute(
            """
            SELECT o.business_unit, COUNT(*) AS active_headcount
            FROM employees e
            JOIN organizations o ON e.organization_id = o.organization_id
            WHERE e.employment_status = 'Active'
            GROUP BY o.business_unit
            ORDER BY active_headcount DESC
            """
        ).fetchdf()

    assert isinstance(result, pd.DataFrame)
    assert set(result.columns) == {"business_unit", "active_headcount"}
    assert result["active_headcount"].sum() > 4500

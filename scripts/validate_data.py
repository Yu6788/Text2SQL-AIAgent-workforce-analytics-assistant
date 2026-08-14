from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from atlas_workforce.schema import JOB_LEVELS, REVIEW_CYCLES, TABLES  # noqa: E402


PRIMARY_KEYS = {
    "organizations": "organization_id",
    "employees": "employee_id",
    "talent_reviews": "review_id",
    "development_programs": "program_id",
    "employee_programs": "employee_program_id",
    "internal_moves": "move_id",
}


@dataclass
class ValidationIssue:
    table: str
    check: str
    message: str


class ValidationError(Exception):
    pass


def load_csvs(data_dir: Path) -> dict[str, pd.DataFrame]:
    frames = {}
    missing = []
    for table in TABLES:
        path = data_dir / f"{table}.csv"
        if not path.exists():
            missing.append(str(path))
            continue
        frames[table] = pd.read_csv(path, parse_dates=True)
    if missing:
        raise ValidationError(f"Missing generated CSV files: {', '.join(missing)}")
    return frames


def _as_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _add_if(condition: bool, issues: list[ValidationIssue], table: str, check: str, message: str) -> None:
    if condition:
        issues.append(ValidationIssue(table, check, message))


def validate_frames(frames: dict[str, pd.DataFrame]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for table, pk in PRIMARY_KEYS.items():
        frame = frames[table]
        _add_if(frame[pk].isna().any(), issues, table, "primary_key_not_null", f"{pk} contains nulls")
        _add_if(not frame[pk].is_unique, issues, table, "primary_key_unique", f"{pk} is not unique")

    org_ids = set(frames["organizations"]["organization_id"])
    employee_ids = set(frames["employees"]["employee_id"])
    program_ids = set(frames["development_programs"]["program_id"])

    employees = frames["employees"]
    _add_if(
        not set(employees["organization_id"]).issubset(org_ids),
        issues,
        "employees",
        "fk_organization_id",
        "employees.organization_id contains invalid references",
    )
    manager_ids = set(employees["manager_id"].dropna())
    _add_if(
        not manager_ids.issubset(employee_ids),
        issues,
        "employees",
        "fk_manager_id",
        "employees.manager_id contains invalid references",
    )
    hire_dates = _as_date(employees["hire_date"])
    termination_dates = _as_date(employees["termination_date"])
    _add_if(
        ((termination_dates.notna()) & (termination_dates <= hire_dates)).any(),
        issues,
        "employees",
        "termination_after_hire",
        "termination_date must be after hire_date",
    )

    reviews = frames["talent_reviews"]
    _add_if(
        not set(reviews["employee_id"]).issubset(employee_ids),
        issues,
        "talent_reviews",
        "fk_employee_id",
        "talent_reviews.employee_id contains invalid references",
    )
    review_dates = _as_date(reviews["review_date"])
    review_employee_hires = reviews.merge(
        employees[["employee_id", "hire_date"]], on="employee_id", how="left"
    )
    _add_if(
        (_as_date(review_employee_hires["review_date"]) < _as_date(review_employee_hires["hire_date"])).any(),
        issues,
        "talent_reviews",
        "review_after_hire",
        "review_date must be on or after hire_date",
    )
    for cycle, expected_date in REVIEW_CYCLES.items():
        cycle_dates = review_dates[reviews["review_cycle"] == cycle]
        if not cycle_dates.empty:
            expected = pd.Timestamp(expected_date)
            too_far = (cycle_dates - expected).abs() > pd.Timedelta(days=45)
            _add_if(
                too_far.any(),
                issues,
                "talent_reviews",
                "review_cycle_date",
                f"{cycle} review dates should be within 45 days of {expected_date}",
            )
    _add_if(
        not reviews["performance_rating"].between(1, 5).all()
        or not reviews["potential_rating"].between(1, 5).all(),
        issues,
        "talent_reviews",
        "rating_range",
        "ratings must be between 1 and 5",
    )

    employee_programs = frames["employee_programs"]
    _add_if(
        not set(employee_programs["employee_id"]).issubset(employee_ids),
        issues,
        "employee_programs",
        "fk_employee_id",
        "employee_programs.employee_id contains invalid references",
    )
    _add_if(
        not set(employee_programs["program_id"]).issubset(program_ids),
        issues,
        "employee_programs",
        "fk_program_id",
        "employee_programs.program_id contains invalid references",
    )
    enrollment_dates = _as_date(employee_programs["enrollment_date"])
    completion_dates = _as_date(employee_programs["completion_date"])
    _add_if(
        ((completion_dates.notna()) & (completion_dates < enrollment_dates)).any(),
        issues,
        "employee_programs",
        "completion_after_enrollment",
        "completion_date must be on or after enrollment_date",
    )

    moves = frames["internal_moves"]
    _add_if(
        not set(moves["employee_id"]).issubset(employee_ids),
        issues,
        "internal_moves",
        "fk_employee_id",
        "internal_moves.employee_id contains invalid references",
    )
    _add_if(
        not set(moves["from_organization_id"]).issubset(org_ids)
        or not set(moves["to_organization_id"]).issubset(org_ids),
        issues,
        "internal_moves",
        "fk_organization_ids",
        "internal_moves organization references contain invalid values",
    )
    move_employee_hires = moves.merge(employees[["employee_id", "hire_date"]], on="employee_id", how="left")
    _add_if(
        (_as_date(move_employee_hires["move_date"]) < _as_date(move_employee_hires["hire_date"])).any(),
        issues,
        "internal_moves",
        "move_after_hire",
        "move_date must be on or after hire_date",
    )
    level_rank = {level: idx for idx, level in enumerate(JOB_LEVELS)}
    from_rank = moves["from_job_level"].map(level_rank)
    to_rank = moves["to_job_level"].map(level_rank)
    _add_if(
        ((moves["move_type"] == "Promotion") & (to_rank <= from_rank)).any(),
        issues,
        "internal_moves",
        "promotion_increases_level",
        "promotion moves must increase job level",
    )
    _add_if(
        ((moves["move_type"] == "Lateral Transfer") & (to_rank != from_rank)).any(),
        issues,
        "internal_moves",
        "lateral_same_level",
        "lateral transfers must preserve job level",
    )
    _add_if(
        (
            (moves["move_type"] == "Organization Transfer")
            & (moves["from_organization_id"] == moves["to_organization_id"])
        ).any(),
        issues,
        "internal_moves",
        "organization_transfer_changes_org",
        "organization transfers must change organization",
    )

    return issues


def print_summary(frames: dict[str, pd.DataFrame]) -> None:
    for table in TABLES:
        print(f"{table}: {len(frames[table]):,} rows")

    organizations = frames["organizations"]
    employees = frames["employees"].merge(
        organizations[["organization_id", "business_unit"]],
        on="organization_id",
        how="left",
    )
    moves = frames["internal_moves"].merge(
        employees[["employee_id", "business_unit"]],
        on="employee_id",
        how="left",
    )
    promotions = moves[moves["move_type"] == "Promotion"]
    print("\nPromotion rate by business unit, synthetic correlation check:")
    active_counts = employees.groupby("business_unit")["employee_id"].nunique()
    promo_counts = promotions.groupby("business_unit")["employee_id"].nunique()
    rates = ((promo_counts / active_counts) * 100).fillna(0).sort_values(ascending=False)
    for bu, rate in rates.items():
        print(f"  {bu}: {rate:.1f}%")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate generated Atlas Workforce CSV data.")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "generated")
    args = parser.parse_args()
    frames = load_csvs(args.data_dir)
    issues = validate_frames(frames)
    print_summary(frames)
    if issues:
        print("\nValidation failed:")
        for issue in issues:
            print(f"- [{issue.table}] {issue.check}: {issue.message}")
        raise SystemExit(1)
    print("\nValidation passed.")


if __name__ == "__main__":
    main()

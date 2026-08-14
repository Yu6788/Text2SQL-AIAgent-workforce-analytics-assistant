from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from atlas_workforce.schema import (  # noqa: E402
    BUSINESS_UNITS,
    JOB_FAMILIES,
    JOB_LEVELS,
    PROGRAM_TYPES,
    PROMOTION_WEIGHT_BY_BUSINESS_UNIT,
    RANDOM_SEED,
    REGIONS,
    REVIEW_CYCLES,
)


def _random_dates(rng: np.random.Generator, start: str, end: str, size: int) -> pd.Series:
    start_ts = pd.Timestamp(start).value // 10**9
    end_ts = pd.Timestamp(end).value // 10**9
    values = rng.integers(start_ts, end_ts + 1, size=size)
    return pd.Series(pd.to_datetime(values, unit="s").normalize())


def _choice(rng: np.random.Generator, values: list[str], size: int, p: list[float] | None = None) -> np.ndarray:
    return rng.choice(values, size=size, replace=True, p=p)


def build_organizations(rng: np.random.Generator, n: int = 50) -> pd.DataFrame:
    rows = []
    for i in range(1, n + 1):
        bu = BUSINESS_UNITS[(i - 1) % len(BUSINESS_UNITS)]
        rows.append(
            {
                "organization_id": f"ORG{i:03d}",
                "organization_name": f"{bu} Org {i:02d}",
                "business_unit": bu,
                "region": REGIONS[(i - 1) % len(REGIONS)],
                "org_leader_id": None,
                "created_date": _random_dates(rng, "2018-01-01", "2023-12-31", 1).iloc[0],
                "organization_status": "Active" if i <= 48 else "Inactive",
            }
        )
    return pd.DataFrame(rows)


def build_employees(rng: np.random.Generator, organizations: pd.DataFrame, n: int = 5000) -> pd.DataFrame:
    employee_ids = [f"E{i:05d}" for i in range(1, n + 1)]
    hire_dates = pd.concat(
        [
            _random_dates(rng, "2018-01-01", "2024-12-31", 4200),
            _random_dates(rng, "2025-01-01", "2025-12-31", 400),
            _random_dates(rng, "2026-01-01", "2026-12-31", 400),
        ],
        ignore_index=True,
    ).sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)

    levels = _choice(rng, JOB_LEVELS, n, p=[0.16, 0.24, 0.26, 0.20, 0.10, 0.04])
    org_weights = organizations["organization_status"].map({"Active": 1.0, "Inactive": 0.2}).to_numpy()
    org_weights = org_weights / org_weights.sum()
    org_ids = rng.choice(organizations["organization_id"].to_numpy(), size=n, p=org_weights)

    status = _choice(rng, ["Active", "Terminated", "Leave"], n, p=[0.94, 0.04, 0.02]).astype(object)
    termination_dates: list[pd.Timestamp | None] = []
    for idx, (hire, emp_status) in enumerate(zip(hire_dates, status)):
        if emp_status == "Terminated":
            min_term = max(hire + pd.Timedelta(days=120), pd.Timestamp("2024-01-01"))
            if min_term > pd.Timestamp("2026-12-31"):
                status[idx] = "Active"
                termination_dates.append(None)
            else:
                termination_dates.append(_random_dates(rng, str(min_term.date()), "2026-12-31", 1).iloc[0])
        else:
            termination_dates.append(None)

    employees = pd.DataFrame(
        {
            "employee_id": employee_ids,
            "hire_date": hire_dates,
            "termination_date": termination_dates,
            "employment_status": status,
            "job_level": levels,
            "job_family": _choice(rng, JOB_FAMILIES, n),
            "location": _choice(rng, REGIONS, n, p=[0.50, 0.22, 0.20, 0.08]),
            "manager_id": None,
            "organization_id": org_ids,
        }
    )

    manager_pool = employees.loc[employees["job_level"].isin(["L5", "L6", "L7"]), "employee_id"].to_numpy()
    for idx, row in employees.iterrows():
        if row["job_level"] == "L7" or len(manager_pool) == 0:
            continue
        manager_id = rng.choice(manager_pool)
        if manager_id != row["employee_id"]:
            employees.at[idx, "manager_id"] = manager_id

    return employees


def backfill_org_leaders(
    rng: np.random.Generator, organizations: pd.DataFrame, employees: pd.DataFrame
) -> pd.DataFrame:
    organizations = organizations.copy()
    senior = employees[employees["job_level"].isin(["L6", "L7"])]
    for idx, org in organizations.iterrows():
        candidates = senior[senior["organization_id"] == org["organization_id"]]
        if candidates.empty:
            candidates = senior
        organizations.at[idx, "org_leader_id"] = rng.choice(candidates["employee_id"].to_numpy())
    return organizations


def build_talent_reviews(rng: np.random.Generator, employees: pd.DataFrame) -> pd.DataFrame:
    rows = []
    completion_rates = {
        "2024_H1": 0.82,
        "2024_H2": 0.85,
        "2025_H1": 0.89,
        "2025_H2": 0.91,
        "2026_H1": 0.94,
        "2026_H2": 0.93,
    }
    review_id = 1
    for cycle, review_date in REVIEW_CYCLES.items():
        review_ts = pd.Timestamp(review_date)
        eligible = employees[
            (employees["hire_date"] <= review_ts)
            & (
                employees["termination_date"].isna()
                | (pd.to_datetime(employees["termination_date"]) > review_ts)
            )
        ]
        sampled = eligible.sample(n=min(2500, len(eligible)), random_state=RANDOM_SEED + review_id)
        for _, emp in sampled.iterrows():
            cancelled = rng.random() < 0.04
            completed = (not cancelled) and rng.random() < completion_rates[cycle]
            perf = int(rng.choice([1, 2, 3, 4, 5], p=[0.04, 0.14, 0.46, 0.26, 0.10]))
            potential = int(rng.choice([1, 2, 3, 4, 5], p=[0.05, 0.16, 0.44, 0.25, 0.10]))
            rec_prob = 0.03 + (0.08 if perf >= 4 else 0) + (0.08 if potential >= 4 else 0)
            rows.append(
                {
                    "review_id": f"R{review_id:06d}",
                    "employee_id": emp["employee_id"],
                    "review_cycle": cycle,
                    "review_date": review_ts,
                    "performance_rating": perf,
                    "potential_rating": potential,
                    "promotion_recommended": bool(rng.random() < rec_prob),
                    "review_status": "Cancelled" if cancelled else ("Completed" if completed else "Pending"),
                }
            )
            review_id += 1
    return pd.DataFrame(rows)


def build_development_programs(rng: np.random.Generator, n: int = 40) -> pd.DataFrame:
    rows = []
    for i in range(1, n + 1):
        program_type = PROGRAM_TYPES[(i - 1) % len(PROGRAM_TYPES)]
        start = _random_dates(rng, "2024-01-01", "2026-09-30", 1).iloc[0]
        duration = int(rng.integers(45, 181))
        end = min(start + pd.Timedelta(days=duration), pd.Timestamp("2026-12-31"))
        status = "Completed" if end < pd.Timestamp("2026-08-01") else rng.choice(["Planned", "Active", "Completed"])
        rows.append(
            {
                "program_id": f"P{i:03d}",
                "program_name": f"{program_type} {i:02d}",
                "program_type": program_type,
                "start_date": start,
                "end_date": end,
                "target_job_level": rng.choice(JOB_LEVELS[:-1]),
                "program_status": status,
            }
        )
    return pd.DataFrame(rows)


def build_employee_programs(
    rng: np.random.Generator, employees: pd.DataFrame, programs: pd.DataFrame, n: int = 8000
) -> pd.DataFrame:
    rows = []
    activeish = employees[employees["employment_status"].isin(["Active", "Leave"])]
    for i in range(1, n + 1):
        emp = activeish.sample(n=1, random_state=RANDOM_SEED + i).iloc[0]
        program = programs.sample(n=1, random_state=RANDOM_SEED + n + i).iloc[0]
        earliest = max(pd.Timestamp(emp["hire_date"]), pd.Timestamp(program["start_date"]) - pd.Timedelta(days=20))
        latest = min(pd.Timestamp(program["end_date"]), pd.Timestamp("2026-12-31"))
        if earliest > latest:
            earliest = pd.Timestamp(program["start_date"])
        enrollment = _random_dates(rng, str(earliest.date()), str(latest.date()), 1).iloc[0]
        base_completion = 0.70 if program["program_type"] == "Leadership Development" else 0.62
        withdrawn = rng.random() < 0.08
        completed = (not withdrawn) and rng.random() < base_completion and enrollment <= pd.Timestamp(program["end_date"])
        in_progress = (not withdrawn) and (not completed) and pd.Timestamp(program["end_date"]) >= pd.Timestamp("2026-08-01")
        completion_date = None
        score = None
        if completed:
            completion_date = _random_dates(rng, str(enrollment.date()), str(pd.Timestamp(program["end_date"]).date()), 1).iloc[0]
            score = round(float(np.clip(rng.normal(84, 9), 55, 100)), 2)
        rows.append(
            {
                "employee_program_id": f"EP{i:06d}",
                "employee_id": emp["employee_id"],
                "program_id": program["program_id"],
                "enrollment_date": enrollment,
                "completion_date": completion_date,
                "participation_status": "Withdrawn" if withdrawn else ("Completed" if completed else ("In Progress" if in_progress else "Enrolled")),
                "completion_score": score,
            }
        )
    return pd.DataFrame(rows)


def build_internal_moves(
    rng: np.random.Generator,
    employees: pd.DataFrame,
    organizations: pd.DataFrame,
    programs: pd.DataFrame,
    employee_programs: pd.DataFrame,
    n: int = 3000,
) -> pd.DataFrame:
    emp_with_bu = employees.merge(
        organizations[["organization_id", "business_unit"]],
        on="organization_id",
        how="left",
    )
    leadership_programs = programs.loc[
        programs["program_type"] == "Leadership Development", "program_id"
    ]
    leadership_completions = employee_programs[
        employee_programs["program_id"].isin(leadership_programs)
        & (employee_programs["participation_status"] == "Completed")
    ][["employee_id", "completion_date"]]
    leadership_employee_ids = set(leadership_completions["employee_id"])

    promotable = emp_with_bu[emp_with_bu["job_level"] != "L7"].copy()
    weights = promotable["business_unit"].map(PROMOTION_WEIGHT_BY_BUSINESS_UNIT).fillna(1.0).to_numpy()
    weights *= promotable["employee_id"].isin(leadership_employee_ids).map({True: 1.85, False: 1.0}).to_numpy()
    weights = weights / weights.sum()

    move_types = ["Promotion"] * 650 + ["Lateral Transfer"] * 850 + ["Organization Transfer"] * 950 + ["Role Change"] * 550
    rng.shuffle(move_types)
    rows = []
    org_ids = organizations["organization_id"].to_numpy()
    for i, move_type in enumerate(move_types[:n], start=1):
        if move_type == "Promotion":
            emp = promotable.iloc[int(rng.choice(np.arange(len(promotable)), p=weights))]
        else:
            emp = emp_with_bu.sample(n=1, random_state=RANDOM_SEED + i).iloc[0]
        from_level = emp["job_level"]
        to_level = from_level
        if move_type == "Promotion":
            to_level = JOB_LEVELS[min(JOB_LEVELS.index(from_level) + 1, len(JOB_LEVELS) - 1)]
        elif move_type == "Role Change" and rng.random() < 0.15 and from_level != "L7":
            to_level = JOB_LEVELS[JOB_LEVELS.index(from_level) + 1]

        from_org = emp["organization_id"]
        to_org = from_org
        if move_type == "Organization Transfer" or (move_type == "Role Change" and rng.random() < 0.35):
            choices = org_ids[org_ids != from_org]
            to_org = rng.choice(choices)

        min_date = max(pd.Timestamp(emp["hire_date"]) + pd.Timedelta(days=90), pd.Timestamp("2024-01-01"))
        emp_completion = leadership_completions[leadership_completions["employee_id"] == emp["employee_id"]]
        if move_type == "Promotion" and not emp_completion.empty and rng.random() < 0.75:
            min_date = max(min_date, pd.Timestamp(emp_completion["completion_date"].min()) + pd.Timedelta(days=30))
        max_date = pd.Timestamp("2026-12-31")
        if pd.notna(emp["termination_date"]):
            max_date = min(max_date, pd.Timestamp(emp["termination_date"]) - pd.Timedelta(days=1))
        if min_date > max_date:
            min_date = max(pd.Timestamp(emp["hire_date"]), pd.Timestamp("2024-01-01"))
            max_date = pd.Timestamp("2026-12-31")
        rows.append(
            {
                "move_id": f"M{i:06d}",
                "employee_id": emp["employee_id"],
                "move_date": _random_dates(rng, str(min_date.date()), str(max_date.date()), 1).iloc[0],
                "move_type": move_type,
                "from_organization_id": from_org,
                "to_organization_id": to_org,
                "from_job_level": from_level,
                "to_job_level": to_level,
            }
        )
    return pd.DataFrame(rows)


def generate_all(seed: int = RANDOM_SEED) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    organizations = build_organizations(rng)
    employees = build_employees(rng, organizations)
    organizations = backfill_org_leaders(rng, organizations, employees)
    talent_reviews = build_talent_reviews(rng, employees)
    development_programs = build_development_programs(rng)
    employee_programs = build_employee_programs(rng, employees, development_programs)
    internal_moves = build_internal_moves(
        rng,
        employees,
        organizations,
        development_programs,
        employee_programs,
    )
    return {
        "organizations": organizations,
        "employees": employees,
        "talent_reviews": talent_reviews,
        "development_programs": development_programs,
        "employee_programs": employee_programs,
        "internal_moves": internal_moves,
    }


def write_csvs(frames: dict[str, pd.DataFrame], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for table, frame in frames.items():
        frame.to_csv(output_dir / f"{table}.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic Atlas Workforce synthetic data.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "generated")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args()
    frames = generate_all(args.seed)
    write_csvs(frames, args.output_dir)
    for table, frame in frames.items():
        print(f"{table}: {len(frame):,} rows")
    print(f"Wrote CSVs to {args.output_dir}")


if __name__ == "__main__":
    main()

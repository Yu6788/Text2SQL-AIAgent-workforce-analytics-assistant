from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from atlas_workforce.schema import TABLES  # noqa: E402


def build_database(data_dir: Path, database_path: Path) -> None:
    missing = [table for table in TABLES if not (data_dir / f"{table}.csv").exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing CSV files for: {', '.join(missing)}. Run scripts/generate_data.py first."
        )

    database_path.parent.mkdir(parents=True, exist_ok=True)
    if database_path.exists():
        database_path.unlink()

    with duckdb.connect(str(database_path)) as con:
        for table in TABLES:
            csv_path = (data_dir / f"{table}.csv").as_posix()
            con.execute(f"CREATE TABLE {table} AS SELECT * FROM read_csv_auto(?, header = true)", [csv_path])

        con.execute("ALTER TABLE organizations ADD PRIMARY KEY (organization_id)")
        con.execute("ALTER TABLE employees ADD PRIMARY KEY (employee_id)")
        con.execute("ALTER TABLE talent_reviews ADD PRIMARY KEY (review_id)")
        con.execute("ALTER TABLE development_programs ADD PRIMARY KEY (program_id)")
        con.execute("ALTER TABLE employee_programs ADD PRIMARY KEY (employee_program_id)")
        con.execute("ALTER TABLE internal_moves ADD PRIMARY KEY (move_id)")

        con.execute(
            "CREATE INDEX idx_employees_org ON employees(organization_id)"
        )
        con.execute(
            "CREATE INDEX idx_reviews_employee ON talent_reviews(employee_id)"
        )
        con.execute(
            "CREATE INDEX idx_employee_programs_employee ON employee_programs(employee_id)"
        )
        con.execute(
            "CREATE INDEX idx_internal_moves_employee ON internal_moves(employee_id)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the local Atlas Workforce DuckDB database.")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "generated")
    parser.add_argument("--database-path", type=Path, default=ROOT / "data" / "atlas_workforce.duckdb")
    args = parser.parse_args()
    build_database(args.data_dir, args.database_path)
    print(f"Built DuckDB database at {args.database_path}")


if __name__ == "__main__":
    main()

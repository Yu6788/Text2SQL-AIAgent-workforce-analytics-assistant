from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import duckdb
from pydantic import BaseModel


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[tuple]
    row_count: int
    truncated: bool
    execution_time_ms: float


@dataclass(frozen=True)
class DuckDBExecutor:
    database_path: Path
    read_only: bool = True
    max_result_rows: int = 200
    query_timeout_seconds: int = 10

    def execute(self, sql: str) -> QueryResult:
        if not self.database_path.exists():
            raise FileNotFoundError(f"DuckDB database not found: {self.database_path}")

        wrapped_sql = f"SELECT * FROM ({sql}) AS result LIMIT {self.max_result_rows + 1}"
        started = time.perf_counter()
        with duckdb.connect(str(self.database_path), read_only=self.read_only) as con:
            cursor = con.execute(wrapped_sql)
            raw_rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]

        elapsed = (time.perf_counter() - started) * 1000
        truncated = len(raw_rows) > self.max_result_rows
        rows = raw_rows[: self.max_result_rows]
        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
            execution_time_ms=elapsed,
        )

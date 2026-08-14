from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import sqlglot
from pydantic import BaseModel
from sqlglot import exp

from atlas_workforce.schema import TABLES


class SQLValidationResult(BaseModel):
    is_valid: bool
    normalized_sql: Optional[str]
    tables_used: list[str]
    error_type: Optional[str]
    error_message: Optional[str]


@dataclass(frozen=True)
class SQLValidator:
    dialect: str = "duckdb"
    allowed_tables: set[str] = field(default_factory=lambda: set(TABLES))
    allow_cross_join: bool = False

    def validate(self, sql: str) -> SQLValidationResult:
        try:
            statements = sqlglot.parse(sql, read=self.dialect)
        except Exception as exc:
            return SQLValidationResult(
                is_valid=False,
                normalized_sql=None,
                tables_used=[],
                error_type="SQL_PARSE_ERROR",
                error_message=str(exc),
            )

        if len(statements) != 1:
            return self._invalid("UNSAFE_SQL", "Exactly one SQL statement is allowed.", [])

        statement = statements[0]
        if not self._is_read_only_select(statement):
            return self._invalid("UNSAFE_SQL", "Only SELECT and WITH ... SELECT queries are allowed.", [])

        if self._contains_external_access(statement):
            return self._invalid("EXTERNAL_ACCESS_ATTEMPT", "External file, URL, extension, or table access is not allowed.", [])

        if not self.allow_cross_join and self._contains_cross_join(statement):
            return self._invalid("CROSS_JOIN_NOT_ALLOWED", "CROSS JOIN is not allowed in V1.", [])

        cte_names = {
            cte.alias_or_name.lower()
            for cte in statement.find_all(exp.CTE)
            if cte.alias_or_name
        }
        tables_used = sorted(
            {
                table.name.lower()
                for table in statement.find_all(exp.Table)
                if table.name and table.name.lower() not in cte_names
            }
        )
        unauthorized = [table for table in tables_used if table not in self.allowed_tables]
        if unauthorized:
            return self._invalid(
                "UNAUTHORIZED_TABLE",
                f"Unauthorized table(s): {', '.join(unauthorized)}",
                tables_used,
            )

        return SQLValidationResult(
            is_valid=True,
            normalized_sql=statement.sql(dialect=self.dialect),
            tables_used=tables_used,
            error_type=None,
            error_message=None,
        )

    def _invalid(self, error_type: str, message: str, tables_used: list[str]) -> SQLValidationResult:
        return SQLValidationResult(
            is_valid=False,
            normalized_sql=None,
            tables_used=tables_used,
            error_type=error_type,
            error_message=message,
        )

    def _is_read_only_select(self, statement: exp.Expression) -> bool:
        if isinstance(statement, exp.Select):
            return True
        if isinstance(statement, exp.Union):
            return True
        if isinstance(statement, exp.With):
            return isinstance(statement.this, exp.Select)
        return isinstance(statement, exp.Select) or statement.find(exp.Select) is statement

    def _contains_cross_join(self, statement: exp.Expression) -> bool:
        for join in statement.find_all(exp.Join):
            if str(join.args.get("kind", "")).upper() == "CROSS":
                return True
            if join.args.get("side") is None and join.args.get("on") is None and join.args.get("using") is None:
                return True
        return False

    def _contains_external_access(self, statement: exp.Expression) -> bool:
        disallowed_command_names = {
            "ATTACH",
            "COPY",
            "DETACH",
            "INSTALL",
            "LOAD",
            "PRAGMA",
            "READ_CSV",
            "READ_CSV_AUTO",
            "READ_JSON",
            "READ_PARQUET",
            "SCAN",
        }
        for command in statement.find_all(exp.Command):
            command_text = command.sql(dialect=self.dialect).upper()
            if any(name in command_text for name in disallowed_command_names):
                return True
        for function in statement.find_all(exp.Func):
            name = function.sql_name().upper()
            if name in disallowed_command_names or name.startswith("READ_"):
                return True
        for anonymous in statement.find_all(exp.Anonymous):
            name = str(anonymous.name).upper()
            if name in disallowed_command_names or name.startswith("READ_"):
                return True
        for table in statement.find_all(exp.Table):
            if isinstance(table.this, exp.Anonymous):
                return True
        return False

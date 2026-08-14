from __future__ import annotations

from decimal import Decimal
from typing import Any


def normalize_value(value: Any, float_precision: int = 6) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return round(float(value), float_precision)
    if isinstance(value, float):
        return round(value, float_precision)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def normalize_rows(
    columns: list[str],
    rows: list[tuple],
    order_sensitive: bool = False,
) -> list[tuple]:
    normalized = [
        tuple(normalize_value(value) for value in row)
        for row in rows
    ]
    if order_sensitive:
        return normalized
    return sorted(normalized, key=lambda row: repr(row))


def results_equivalent(
    gold_columns: list[str],
    gold_rows: list[tuple],
    generated_columns: list[str],
    generated_rows: list[tuple],
    order_sensitive: bool = False,
) -> bool:
    if len(gold_columns) != len(generated_columns):
        return False

    gold_normalized = normalize_rows(gold_columns, gold_rows, order_sensitive)
    generated_normalized = normalize_rows(generated_columns, generated_rows, order_sensitive)
    return gold_normalized == generated_normalized

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class TableDocument:
    table_name: str
    text: str
    metadata: dict[str, Any]


def load_table_metadata(metadata_dir: Path) -> list[dict[str, Any]]:
    table_dir = metadata_dir / "tables"
    if not table_dir.exists():
        raise FileNotFoundError(f"Metadata table directory not found: {table_dir}")

    records = []
    for path in sorted(table_dir.glob("*.yaml")):
        with path.open("r", encoding="utf-8") as handle:
            record = yaml.safe_load(handle)
        if not isinstance(record, dict) or "table_name" not in record:
            raise ValueError(f"Invalid table metadata file: {path}")
        records.append(record)
    if not records:
        raise ValueError(f"No table metadata YAML files found in {table_dir}")
    return records


def _format_columns(columns: list[dict[str, Any]]) -> str:
    parts = []
    for column in columns:
        name = column.get("name", "")
        col_type = column.get("type", "")
        description = column.get("description", "")
        parts.append(f"- {name} ({col_type}): {description}")
    return "\n".join(parts)


def _format_foreign_keys(foreign_keys: dict[str, Any] | None) -> str:
    if not foreign_keys:
        return "None"
    parts = []
    for column, config in foreign_keys.items():
        if isinstance(config, dict):
            target = config.get("references", "")
        else:
            target = str(config)
        parts.append(f"- {column} -> {target}")
    return "\n".join(parts)


def _format_sample_rows(sample_rows: list[dict[str, Any]] | None) -> str:
    if not sample_rows:
        return "None"
    formatted = []
    for row in sample_rows[:2]:
        pairs = [f"{key}={value}" for key, value in row.items()]
        formatted.append("- " + ", ".join(pairs))
    return "\n".join(formatted)


def serialize_table_document(record: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Table: {record['table_name']}",
            f"Description: {record.get('description', '').strip()}",
            f"Grain: {record.get('grain', '').strip()}",
            f"Primary key: {', '.join(record.get('primary_key', []))}",
            "Foreign keys:",
            _format_foreign_keys(record.get("foreign_keys")),
            "Columns:",
            _format_columns(record.get("columns", [])),
            "Sample rows:",
            _format_sample_rows(record.get("sample_rows")),
        ]
    )


def build_table_documents(metadata_dir: Path) -> list[TableDocument]:
    records = load_table_metadata(metadata_dir)
    documents = []
    for record in records:
        documents.append(
            TableDocument(
                table_name=record["table_name"],
                text=serialize_table_document(record),
                metadata=record,
            )
        )
    return documents

from __future__ import annotations

from pathlib import Path
import os
from typing import Optional

import yaml
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parents[3]


class ProjectSettings(BaseModel):
    name: str
    environment: str = "development"


class LLMSettings(BaseModel):
    provider: str = "stub"
    model: str = "deterministic_sql_rules_v1"
    base_url: Optional[str] = None


class DataSettings(BaseModel):
    random_seed: int = 42
    generated_dir: Path
    database_path: Path


class DatabaseSettings(BaseModel):
    type: str = "duckdb"
    path: Path
    read_only: bool = True
    query_timeout_seconds: int = 10
    max_result_rows: int = 200


class RagSettings(BaseModel):
    embedding_model: str
    reranker_model: str
    retrieval_top_k: int = 20
    rerank_top_k: int = 4
    max_metadata_tokens: int = 450


class VectorStoreSettings(BaseModel):
    type: str = "faiss"
    index_type: str = "IndexFlatIP"
    index_path: Path


class SqlSettings(BaseModel):
    dialect: str = "duckdb"
    max_repair_attempts: int = 3
    allow_cross_join: bool = False


class ApiSettings(BaseModel):
    request_timeout_seconds: int = 30
    max_attempts: int = 3
    initial_backoff_seconds: int = 1
    max_backoff_seconds: int = 8


class StructuredOutputSettings(BaseModel):
    max_retries: int = 1


class PromptSettings(BaseModel):
    guardrail: str
    sql_generation: str
    sql_repair: str
    summary: str


class LoggingSettings(BaseModel):
    enabled: bool = True
    log_path: Path
    level: str = "INFO"


class Settings(BaseModel):
    project: ProjectSettings
    llm: LLMSettings = Field(default_factory=LLMSettings)
    data: DataSettings
    database: DatabaseSettings
    rag: RagSettings
    vector_store: VectorStoreSettings
    sql: SqlSettings
    api: ApiSettings
    structured_output: StructuredOutputSettings
    prompts: PromptSettings
    logging: LoggingSettings

    model_config = {"arbitrary_types_allowed": True}

    def resolve_paths(self, root: Path = ROOT) -> "Settings":
        data = self.model_copy(deep=True)
        for obj, fields in [
            (data.data, ["generated_dir", "database_path"]),
            (data.database, ["path"]),
            (data.vector_store, ["index_path"]),
            (data.logging, ["log_path"]),
        ]:
            for field in fields:
                value = getattr(obj, field)
                if not value.is_absolute():
                    setattr(obj, field, root / value)
        return data


def load_settings(path: Path | str = ROOT / "config.yaml") -> Settings:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    return Settings.model_validate(raw).resolve_paths(config_path.parent)


def load_env_file(path: Path | str = ROOT / ".env") -> dict[str, str]:
    env_path = Path(path)
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_env_value(key: str, env_file: dict[str, str] | None = None) -> str | None:
    if key in os.environ:
        return os.environ[key]
    if env_file and key in env_file:
        return env_file[key]
    return None


def load_prompt(prompt_name: str, prompt_dir: Path = ROOT / "src" / "atlas_workforce" / "prompts") -> str:
    path = prompt_dir / f"{prompt_name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")

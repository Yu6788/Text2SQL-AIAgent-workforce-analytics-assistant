from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from atlas_workforce.config.settings import Settings, get_env_value, load_env_file
from atlas_workforce.schema import TABLES


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    passed: bool
    message: str


def check_file(path: Path, name: str, fix: str) -> PreflightCheck:
    if path.exists():
        return PreflightCheck(name, True, f"Found {path}")
    return PreflightCheck(name, False, f"Missing {path}. {fix}")


def run_preflight(settings: Settings, root: Path, env_path: Path) -> list[PreflightCheck]:
    checks: list[PreflightCheck] = []

    checks.append(
        check_file(
            settings.database.path,
            "DuckDB database",
            "Run: python3 scripts/build_database.py",
        )
    )

    for table in TABLES:
        checks.append(
            check_file(
                settings.data.generated_dir / f"{table}.csv",
                f"Generated CSV: {table}",
                "Run: python3 scripts/generate_data.py",
            )
        )

    checks.append(
        check_file(
            settings.vector_store.index_path / "backend.txt",
            "Vector index backend marker",
            "Run: python3 scripts/build_vector_index.py --embedding-backend hashing --vector-backend numpy",
        )
    )
    backend_path = settings.vector_store.index_path / "backend.txt"
    if backend_path.exists():
        backend = backend_path.read_text(encoding="utf-8").strip()
        index_file = "index.faiss" if backend == "faiss" else "embeddings.npy"
        checks.append(
            check_file(
                settings.vector_store.index_path / index_file,
                f"Vector index file ({backend})",
                "Rebuild the vector index.",
            )
        )

    checks.append(
        check_file(
            root / "metadata" / "business_context.yaml",
            "Business context metadata",
            "Restore metadata/business_context.yaml.",
        )
    )
    for table in TABLES:
        checks.append(
            check_file(
                root / "metadata" / "tables" / f"{table}.yaml",
                f"Table metadata: {table}",
                "Restore metadata/tables YAML files.",
            )
        )

    for prompt_name in [
        settings.prompts.guardrail,
        settings.prompts.sql_generation,
        settings.prompts.sql_repair,
        settings.prompts.summary,
    ]:
        checks.append(
            check_file(
                root / "src" / "atlas_workforce" / "prompts" / f"{prompt_name}.txt",
                f"Prompt: {prompt_name}",
                "Restore prompt files under src/atlas_workforce/prompts.",
            )
        )

    env_values = load_env_file(env_path)
    provider = get_env_value("LLM_PROVIDER", env_values) or settings.llm.provider
    model = get_env_value("LLM_MODEL", env_values) or settings.llm.model
    base_url = get_env_value("LLM_BASE_URL", env_values) or settings.llm.base_url
    api_key = get_env_value("LLM_API_KEY", env_values)

    checks.append(
        PreflightCheck(
            "LLM provider",
            bool(provider),
            f"Configured provider: {provider or 'missing'}",
        )
    )
    checks.append(
        PreflightCheck(
            "LLM model",
            bool(model and "<" not in model),
            "LLM model is configured." if model and "<" not in model else "LLM model is missing or still a placeholder.",
        )
    )

    if provider in {"stub", "local_stub"}:
        checks.append(PreflightCheck("LLM API key", True, "Stub provider does not require an API key."))
    else:
        checks.append(
            PreflightCheck(
                "LLM API key",
                bool(api_key and "<" not in api_key),
                "LLM API key is set." if api_key and "<" not in api_key else "LLM_API_KEY is missing or still a placeholder.",
            )
        )
        checks.append(
            PreflightCheck(
                "LLM base URL",
                bool(base_url and "<" not in str(base_url)),
                "LLM base URL is configured." if base_url and "<" not in str(base_url) else "LLM_BASE_URL is missing or still a placeholder.",
            )
        )

    return checks

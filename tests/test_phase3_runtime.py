from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from atlas_workforce.config.settings import load_prompt, load_settings  # noqa: E402
from atlas_workforce.graph.workflow import WorkflowServices, create_workflow, initial_state  # noqa: E402
from atlas_workforce.llm.service import StubLLMService  # noqa: E402
from atlas_workforce.rag.documents import build_table_documents  # noqa: E402
from atlas_workforce.rag.embeddings import HashingEmbedder  # noqa: E402
from atlas_workforce.rag.reranker import LexicalReranker  # noqa: E402
from atlas_workforce.rag.retrieval import build_in_memory_store  # noqa: E402
from atlas_workforce.runtime import RuntimeOptions, run_question  # noqa: E402
from atlas_workforce.sql.executor import DuckDBExecutor  # noqa: E402
from atlas_workforce.sql.validator import SQLValidator  # noqa: E402


def test_settings_and_prompts_load() -> None:
    settings = load_settings(ROOT / "config.yaml")

    assert settings.database.path == ROOT / "data" / "atlas_workforce.duckdb"
    assert settings.sql.dialect == "duckdb"
    assert "DuckDB SQL" in load_prompt(settings.prompts.sql_generation)


def test_sql_validator_allows_safe_select_and_extracts_tables() -> None:
    validator = SQLValidator()
    result = validator.validate(
        """
        WITH active_employees AS (
            SELECT employee_id, organization_id
            FROM employees
            WHERE employment_status = 'Active'
        )
        SELECT o.business_unit, COUNT(*) AS active_headcount
        FROM active_employees e
        JOIN organizations o ON e.organization_id = o.organization_id
        GROUP BY o.business_unit
        """
    )

    assert result.is_valid
    assert result.tables_used == ["employees", "organizations"]
    assert result.normalized_sql is not None


@pytest.mark.parametrize(
    ("sql", "error_type"),
    [
        ("DROP TABLE employees", "UNSAFE_SQL"),
        ("INSERT INTO employees SELECT * FROM employees", "UNSAFE_SQL"),
        ("PRAGMA show_tables", "UNSAFE_SQL"),
        ("SELECT * FROM salaries", "UNAUTHORIZED_TABLE"),
        ("SELECT * FROM employees CROSS JOIN organizations", "CROSS_JOIN_NOT_ALLOWED"),
        ("SELECT * FROM read_csv_auto('secret.csv')", "EXTERNAL_ACCESS_ATTEMPT"),
        ("SELECT * FROM read_parquet('secret.parquet')", "EXTERNAL_ACCESS_ATTEMPT"),
    ],
)
def test_sql_validator_rejects_unsafe_sql(sql: str, error_type: str) -> None:
    result = SQLValidator().validate(sql)

    assert not result.is_valid
    assert result.error_type == error_type


def test_duckdb_executor_runs_read_only_query() -> None:
    executor = DuckDBExecutor(
        database_path=ROOT / "data" / "atlas_workforce.duckdb",
        read_only=True,
        max_result_rows=3,
    )
    result = executor.execute("SELECT employee_id FROM employees ORDER BY employee_id")

    assert result.columns == ["employee_id"]
    assert result.row_count == 3
    assert result.truncated


def test_stub_workflow_success() -> None:
    settings = load_settings(ROOT / "config.yaml")
    documents = build_table_documents(ROOT / "metadata")
    embedder = HashingEmbedder()
    services = WorkflowServices(
        llm=StubLLMService(),
        validator=SQLValidator(),
        executor=DuckDBExecutor(
            database_path=settings.database.path,
            read_only=True,
            max_result_rows=10,
        ),
        business_context="business context",
        schema_context="\n\n".join(document.text for document in documents),
        embedder=embedder,
        vector_store=build_in_memory_store(ROOT / "metadata", embedder),
        reranker=LexicalReranker(),
    )
    app = create_workflow(services)
    final_state = app.invoke(initial_state("How many active employees are in each business unit?"))

    assert final_state["status"] == "SUCCESS"
    assert final_state["retrieved_tables"][:2] == ["employees", "organizations"]
    assert len(final_state["retrieved_tables"]) == 4
    assert final_state["validation_result"]["is_valid"]
    assert final_state["db_result"]["row_count"] > 0
    assert "business_unit" in final_state["db_result"]["columns"]


@pytest.mark.parametrize(
    "question",
    [
        "How many active employees are in each business unit?",
        "Which organization has the highest active headcount?",
        "What was the 2026 H1 talent review completion rate?",
        "Which business unit had the best 2026 H1 reviews?",
    ],
)
def test_main_streamlit_examples_work_in_offline_demo(question: str) -> None:
    settings = load_settings(ROOT / "config.yaml")
    final_state = run_question(
        settings,
        ROOT,
        question,
        RuntimeOptions(llm_provider="stub", embedding_backend="hashing", reranker_backend="lexical"),
    )

    assert final_state["status"] == "SUCCESS"
    assert final_state["final_answer"]
    assert final_state["validation_result"]["is_valid"]
    assert final_state["db_result"]["row_count"] > 0


def test_stub_workflow_guardrail_rejection() -> None:
    settings = load_settings(ROOT / "config.yaml")
    services = WorkflowServices(
        llm=StubLLMService(),
        validator=SQLValidator(),
        executor=DuckDBExecutor(database_path=settings.database.path),
        business_context="business context",
        schema_context="schema context",
    )
    app = create_workflow(services)
    final_state = app.invoke(initial_state("What is the weather today?"))

    assert final_state["status"] == "REJECTED_BY_GUARDRAIL"
    assert not final_state["guardrail_allowed"]
    assert "retrieved_tables" not in final_state


def test_workflow_sql_generation_receives_retrieved_context_only() -> None:
    class RecordingLLM(StubLLMService):
        seen_schema_context = ""

        def generate_sql(self, question: str, business_context: str, schema_context: str):
            self.seen_schema_context = schema_context
            return super().generate_sql(question, business_context, schema_context)

    settings = load_settings(ROOT / "config.yaml")
    documents = build_table_documents(ROOT / "metadata")
    embedder = HashingEmbedder()
    llm = RecordingLLM()
    services = WorkflowServices(
        llm=llm,
        validator=SQLValidator(),
        executor=DuckDBExecutor(
            database_path=settings.database.path,
            read_only=True,
            max_result_rows=10,
        ),
        business_context="business context",
        schema_context="\n\n".join(document.text for document in documents),
        embedder=embedder,
        vector_store=build_in_memory_store(ROOT / "metadata", embedder),
        reranker=LexicalReranker(),
        rerank_top_k=4,
    )
    app = create_workflow(services)
    app.invoke(initial_state("Which development program had the highest completion rate?"))

    assert "Table: employee_programs" in llm.seen_schema_context
    assert "Table: development_programs" in llm.seen_schema_context
    assert llm.seen_schema_context.count("Table:") == 4


def test_workflow_handles_llm_provider_error_without_traceback() -> None:
    class FailingLLM(StubLLMService):
        def generate_sql(self, question: str, business_context: str, schema_context: str):
            raise RuntimeError("provider quota exceeded")

    settings = load_settings(ROOT / "config.yaml")
    documents = build_table_documents(ROOT / "metadata")
    embedder = HashingEmbedder()
    services = WorkflowServices(
        llm=FailingLLM(),
        validator=SQLValidator(),
        executor=DuckDBExecutor(database_path=settings.database.path),
        business_context="business context",
        schema_context="\n\n".join(document.text for document in documents),
        embedder=embedder,
        vector_store=build_in_memory_store(ROOT / "metadata", embedder),
        reranker=LexicalReranker(),
    )
    app = create_workflow(services)
    final_state = app.invoke(initial_state("How many active employees are in each business unit?"))

    assert final_state["status"] == "API_ERROR"
    assert final_state["db_error"] == "provider quota exceeded"


def test_workflow_repairs_validator_failure() -> None:
    settings = load_settings(ROOT / "config.yaml")
    documents = build_table_documents(ROOT / "metadata")
    embedder = HashingEmbedder()
    services = WorkflowServices(
        llm=StubLLMService(),
        validator=SQLValidator(),
        executor=DuckDBExecutor(database_path=settings.database.path, read_only=True),
        business_context="business context",
        schema_context="\n\n".join(document.text for document in documents),
        embedder=embedder,
        vector_store=build_in_memory_store(ROOT / "metadata", embedder),
        reranker=LexicalReranker(),
    )
    app = create_workflow(services)
    final_state = app.invoke(initial_state("Repair demo unsafe: how many active employees are there?"))

    assert final_state["status"] == "SUCCESS"
    assert final_state["sql_retry_count"] == 1
    assert "Unauthorized table" in final_state["retry_history"][0]


def test_workflow_repairs_database_binder_failure() -> None:
    settings = load_settings(ROOT / "config.yaml")
    documents = build_table_documents(ROOT / "metadata")
    embedder = HashingEmbedder()
    services = WorkflowServices(
        llm=StubLLMService(),
        validator=SQLValidator(),
        executor=DuckDBExecutor(database_path=settings.database.path, read_only=True),
        business_context="business context",
        schema_context="\n\n".join(document.text for document in documents),
        embedder=embedder,
        vector_store=build_in_memory_store(ROOT / "metadata", embedder),
        reranker=LexicalReranker(),
    )
    app = create_workflow(services)
    final_state = app.invoke(initial_state("Repair demo bad column: count employees by employment status."))

    assert final_state["status"] == "SUCCESS"
    assert final_state["sql_retry_count"] == 1
    assert "employee_status" in final_state["retry_history"][0]


def test_runtime_helper_runs_stub_question() -> None:
    settings = load_settings(ROOT / "config.yaml")

    final_state = run_question(
        settings,
        ROOT,
        "How many active employees are in each business unit?",
        RuntimeOptions(llm_provider="stub", embedding_backend="hashing", reranker_backend="lexical"),
    )

    assert final_state["status"] == "SUCCESS"
    assert final_state["retrieved_tables"]


def test_runtime_helper_resolves_follow_up_question() -> None:
    settings = load_settings(ROOT / "config.yaml")
    options = RuntimeOptions(llm_provider="stub", embedding_backend="hashing", reranker_backend="lexical")
    first_state = run_question(
        settings,
        ROOT,
        "How many active employees are in each business unit?",
        options,
    )

    follow_up_state = run_question(
        settings,
        ROOT,
        "What about only Technology?",
        options,
        previous_state=first_state,
        force_follow_up=True,
    )

    assert follow_up_state["is_follow_up"]
    assert follow_up_state["resolved_question"] == "How many active employees are in the Technology business unit?"
    assert follow_up_state["status"] == "SUCCESS"
    assert follow_up_state["db_result"]["rows"] == [("Technology", 668)]

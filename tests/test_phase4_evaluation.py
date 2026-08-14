from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from atlas_workforce.config.settings import load_settings  # noqa: E402
from atlas_workforce.evaluation.result_compare import results_equivalent  # noqa: E402
from atlas_workforce.evaluation.runner import evaluate_cases, load_cases  # noqa: E402
from atlas_workforce.graph.workflow import WorkflowServices  # noqa: E402
from atlas_workforce.llm.service import StubLLMService  # noqa: E402
from atlas_workforce.rag.documents import build_table_documents  # noqa: E402
from atlas_workforce.rag.embeddings import HashingEmbedder  # noqa: E402
from atlas_workforce.rag.reranker import LexicalReranker  # noqa: E402
from atlas_workforce.rag.retrieval import build_in_memory_store  # noqa: E402
from atlas_workforce.sql.executor import DuckDBExecutor  # noqa: E402
from atlas_workforce.sql.validator import SQLValidator  # noqa: E402


def test_results_equivalent_ignores_row_order() -> None:
    assert results_equivalent(
        gold_columns=["business_unit", "headcount"],
        gold_rows=[("Finance", 2), ("People", 1)],
        generated_columns=["business_unit", "headcount"],
        generated_rows=[("People", 1), ("Finance", 2)],
    )


def test_seed_gold_sql_executes() -> None:
    settings = load_settings(ROOT / "config.yaml")
    executor = DuckDBExecutor(database_path=settings.database.path, read_only=True)
    cases = load_cases(ROOT / "evaluation" / "questions_seed.json")

    for case in cases:
        result = executor.execute(case.gold_sql)
        assert result.columns
        assert result.rows


def test_evaluator_runs_stub_subset() -> None:
    settings = load_settings(ROOT / "config.yaml")
    documents = build_table_documents(ROOT / "metadata")
    embedder = HashingEmbedder()
    executor = DuckDBExecutor(database_path=settings.database.path, read_only=True)
    services = WorkflowServices(
        llm=StubLLMService(),
        validator=SQLValidator(),
        executor=executor,
        business_context="business context",
        schema_context="\n\n".join(document.text for document in documents),
        embedder=embedder,
        vector_store=build_in_memory_store(ROOT / "metadata", embedder),
        reranker=LexicalReranker(),
    )
    cases = load_cases(ROOT / "evaluation" / "questions_seed.json")[:3]

    report = evaluate_cases(cases, services, executor)

    assert report["summary"]["total_cases"] == 3
    assert report["summary"]["average_table_recall_at_4"] > 0
    assert report["summary"]["execution_success_rate"] >= 1 / 3


def test_seed_retrieval_recall_is_complete_with_stub_stack() -> None:
    settings = load_settings(ROOT / "config.yaml")
    documents = build_table_documents(ROOT / "metadata")
    embedder = HashingEmbedder()
    executor = DuckDBExecutor(database_path=settings.database.path, read_only=True)
    services = WorkflowServices(
        llm=StubLLMService(),
        validator=SQLValidator(),
        executor=executor,
        business_context="business context",
        schema_context="\n\n".join(document.text for document in documents),
        embedder=embedder,
        vector_store=build_in_memory_store(ROOT / "metadata", embedder),
        reranker=LexicalReranker(),
    )
    cases = load_cases(ROOT / "evaluation" / "questions_seed.json")

    report = evaluate_cases(cases, services, executor)

    assert report["summary"]["average_table_recall_at_4"] == 1.0
    assert report["summary"]["all_required_tables_recall_at_4"] == 1.0


def test_repair_seed_evaluation_recovers_failures() -> None:
    settings = load_settings(ROOT / "config.yaml")
    documents = build_table_documents(ROOT / "metadata")
    embedder = HashingEmbedder()
    executor = DuckDBExecutor(database_path=settings.database.path, read_only=True)
    services = WorkflowServices(
        llm=StubLLMService(),
        validator=SQLValidator(),
        executor=executor,
        business_context="business context",
        schema_context="\n\n".join(document.text for document in documents),
        embedder=embedder,
        vector_store=build_in_memory_store(ROOT / "metadata", embedder),
        reranker=LexicalReranker(),
    )
    cases = load_cases(ROOT / "evaluation" / "repair_questions_seed.json")

    report = evaluate_cases(cases, services, executor)

    assert report["summary"]["cases_with_sql_retries"] == 2
    assert report["summary"]["retry_recovery_rate"] == 1.0
    assert report["summary"]["execution_accuracy"] == 1.0

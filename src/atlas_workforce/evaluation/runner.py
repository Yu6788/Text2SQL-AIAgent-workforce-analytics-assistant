from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atlas_workforce.evaluation.result_compare import results_equivalent
from atlas_workforce.graph.workflow import WorkflowServices, create_workflow, initial_state
from atlas_workforce.sql.executor import DuckDBExecutor, QueryResult


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    question: str
    difficulty: str
    category: str
    expected_tables: list[str]
    gold_sql: str
    notes: str = ""


def load_cases(path: Path) -> list[EvaluationCase]:
    with path.open("r", encoding="utf-8") as handle:
        raw_cases = json.load(handle)
    return [EvaluationCase(**case) for case in raw_cases]


def run_gold_sql(executor: DuckDBExecutor, sql: str) -> QueryResult:
    return executor.execute(sql)


def evaluate_cases(
    cases: list[EvaluationCase],
    services: WorkflowServices,
    gold_executor: DuckDBExecutor,
) -> dict[str, Any]:
    app = create_workflow(services)
    case_results = []

    for case in cases:
        started = time.perf_counter()
        gold_error = None
        generated_error = None
        gold_result = None
        final_state = None
        result_equivalent = False
        retrieval_recall = 0.0
        all_required_tables_retrieved = False

        try:
            gold_result = run_gold_sql(gold_executor, case.gold_sql)
        except Exception as exc:
            gold_error = str(exc)

        try:
            final_state = app.invoke(initial_state(case.question))
        except Exception as exc:
            generated_error = str(exc)

        if final_state:
            retrieved_tables = final_state.get("retrieved_tables", [])
            expected = set(case.expected_tables)
            hits = len(expected & set(retrieved_tables))
            retrieval_recall = hits / len(expected) if expected else 1.0
            all_required_tables_retrieved = hits == len(expected)

            if gold_result and final_state.get("db_result"):
                generated_result = final_state["db_result"]
                result_equivalent = results_equivalent(
                    gold_columns=gold_result.columns,
                    gold_rows=gold_result.rows,
                    generated_columns=generated_result["columns"],
                    generated_rows=generated_result["rows"],
                    order_sensitive=False,
                )
            if final_state.get("db_error"):
                generated_error = final_state["db_error"]

        sql_retry_count = final_state.get("sql_retry_count", 0) if final_state else 0
        retry_history = final_state.get("retry_history", []) if final_state else []
        elapsed_ms = (time.perf_counter() - started) * 1000
        case_results.append(
            {
                "id": case.id,
                "question": case.question,
                "difficulty": case.difficulty,
                "category": case.category,
                "expected_tables": case.expected_tables,
                "retrieved_tables": final_state.get("retrieved_tables", []) if final_state else [],
                "retrieval_recall_at_4": retrieval_recall,
                "all_required_tables_retrieved_at_4": all_required_tables_retrieved,
                "status": final_state.get("status") if final_state else "SYSTEM_ERROR",
                "generated_sql": final_state.get("generated_sql") if final_state else None,
                "validated_tables": final_state.get("validated_tables", []) if final_state else [],
                "execution_success": bool(final_state and final_state.get("db_result")),
                "sql_retry_count": sql_retry_count,
                "retry_history": retry_history,
                "recovered_by_repair": bool(sql_retry_count > 0 and final_state and final_state.get("db_result")),
                "result_equivalent": result_equivalent,
                "gold_error": gold_error,
                "generated_error": generated_error,
                "latency_ms": elapsed_ms,
            }
        )

    total = len(case_results)
    avg_recall = sum(result["retrieval_recall_at_4"] for result in case_results) / total if total else 0
    all_required = sum(result["all_required_tables_retrieved_at_4"] for result in case_results) / total if total else 0
    execution_success = sum(result["execution_success"] for result in case_results) / total if total else 0
    execution_accuracy = sum(result["result_equivalent"] for result in case_results) / total if total else 0
    initial_failures = [result for result in case_results if result["sql_retry_count"] > 0]
    retry_recovery_rate = (
        sum(result["recovered_by_repair"] for result in initial_failures) / len(initial_failures)
        if initial_failures
        else 0
    )
    median_latency = sorted(result["latency_ms"] for result in case_results)[total // 2] if total else 0

    return {
        "summary": {
            "total_cases": total,
            "average_table_recall_at_4": avg_recall,
            "all_required_tables_recall_at_4": all_required,
            "execution_success_rate": execution_success,
            "execution_accuracy": execution_accuracy,
            "retry_recovery_rate": retry_recovery_rate,
            "cases_with_sql_retries": len(initial_failures),
            "median_latency_ms": median_latency,
        },
        "cases": case_results,
    }

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional, Union

from atlas_workforce.llm.service import LLMService
from atlas_workforce.rag.embeddings import Embedder
from atlas_workforce.rag.reranker import Reranker
from atlas_workforce.rag.vector_store import FaissVectorStore, NumpyVectorStore
from atlas_workforce.rag.retrieval import retrieve_tables
from atlas_workforce.sql.executor import DuckDBExecutor
from atlas_workforce.sql.validator import SQLValidator
from atlas_workforce.graph.state import AgentState


@dataclass
class WorkflowServices:
    llm: LLMService
    validator: SQLValidator
    executor: DuckDBExecutor
    business_context: str
    schema_context: str = ""
    embedder: Optional[Embedder] = None
    vector_store: Optional[Union[NumpyVectorStore, FaissVectorStore]] = None
    reranker: Optional[Reranker] = None
    retrieval_top_k: int = 20
    rerank_top_k: int = 4
    max_sql_repair_attempts: int = 3


def create_workflow(services: WorkflowServices):
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:
        raise ImportError(
            "langgraph is required for workflow execution. "
            "Install dependencies with: python3 -m pip install -r requirements.txt"
        ) from exc

    graph = StateGraph(AgentState)

    def guardrail_node(state: AgentState) -> AgentState:
        question_for_pipeline = state.get("resolved_question") or state["user_question"]
        try:
            result = services.llm.guardrail(
                question_for_pipeline,
                "Atlas Workforce analytics tables: employees, organizations, talent_reviews, "
                "development_programs, employee_programs, internal_moves.",
            )
        except Exception as exc:
            return {
                **state,
                "guardrail_allowed": False,
                "guardrail_reason": str(exc),
                "status": "API_ERROR",
            }
        return {
            **state,
            "guardrail_allowed": result.allowed,
            "guardrail_reason": result.reason,
            "status": "GUARDRAIL_PASSED" if result.allowed else "REJECTED_BY_GUARDRAIL",
        }

    def generate_sql_node(state: AgentState) -> AgentState:
        question_for_pipeline = state.get("resolved_question") or state["user_question"]
        try:
            result = services.llm.generate_sql(
                question_for_pipeline,
                services.business_context,
                state.get("retrieved_context") or services.schema_context,
            )
        except Exception as exc:
            return {
                **state,
                "db_error": str(exc),
                "status": "API_ERROR",
            }
        return {
            **state,
            "generated_sql": result.sql,
            "llm_reported_tables": result.tables_used,
            "status": "SQL_GENERATED",
        }

    def retrieval_node(state: AgentState) -> AgentState:
        if services.embedder is None or services.vector_store is None:
            return {
                **state,
                "retrieved_context": services.schema_context,
                "retrieved_candidates": [],
                "retrieved_tables": [],
                "retrieval_scores": {},
                "reranker_scores": {},
                "status": "RETRIEVAL_SKIPPED",
            }
        results = retrieve_tables(
            question=state.get("resolved_question") or state["user_question"],
            embedder=services.embedder,
            store=services.vector_store,
            retrieval_top_k=services.retrieval_top_k,
            rerank_top_k=services.rerank_top_k,
            reranker=services.reranker,
        )
        return {
            **state,
            "retrieved_context": "\n\n".join(result.document for result in results),
            "retrieved_candidates": [
                {
                    "table_name": result.table_name,
                    "retrieval_score": result.retrieval_score,
                    "reranker_score": result.reranker_score,
                }
                for result in results
            ],
            "retrieved_tables": [result.table_name for result in results],
            "retrieval_scores": {
                result.table_name: result.retrieval_score for result in results
            },
            "reranker_scores": {
                result.table_name: result.reranker_score for result in results
            },
            "status": "SCHEMA_RETRIEVED",
        }

    def validate_sql_node(state: AgentState) -> AgentState:
        result = services.validator.validate(state["generated_sql"])
        return {
            **state,
            "validation_result": result.model_dump(),
            "validated_tables": result.tables_used,
            "status": "SQL_VALIDATED" if result.is_valid else result.error_type or "SQL_VALIDATION_FAILED",
        }

    def execute_sql_node(state: AgentState) -> AgentState:
        try:
            result = services.executor.execute(state["validation_result"]["normalized_sql"])
            return {
                **state,
                "db_result": result.model_dump(),
                "db_error": None,
                "result_truncated": result.truncated,
                "status": "DATABASE_EXECUTED",
            }
        except Exception as exc:
            return {
                **state,
                "db_error": str(exc),
                "status": "DATABASE_EXECUTION_ERROR",
            }

    def repair_sql_node(state: AgentState) -> AgentState:
        retry_count = state.get("sql_retry_count", 0) + 1
        retry_history = state.get("retry_history", [])
        current_error = (
            state.get("db_error")
            or state.get("validation_result", {}).get("error_message")
            or state.get("status", "Unknown SQL error")
        )
        try:
            result = services.llm.repair_sql(
                question=state.get("resolved_question") or state["user_question"],
                business_context=services.business_context,
                schema_context=state.get("retrieved_context") or services.schema_context,
                previous_sql=state.get("generated_sql", ""),
                error_message=current_error,
                retry_history=retry_history,
            )
        except Exception as exc:
            return {
                **state,
                "db_error": str(exc),
                "status": "API_ERROR",
            }
        return {
            **state,
            "generated_sql": result.sql,
            "sql_retry_count": retry_count,
            "retry_history": retry_history + [current_error],
            "status": "SQL_REPAIRED",
        }

    def summarize_node(state: AgentState) -> AgentState:
        result_data = state["db_result"]
        try:
            summary = services.llm.summarize(
                question=state.get("resolved_question") or state["user_question"],
                sql=state["generated_sql"],
                columns=result_data["columns"],
                rows=result_data["rows"],
                truncated=result_data["truncated"],
            )
        except Exception as exc:
            return {
                **state,
                "db_error": str(exc),
                "status": "API_ERROR",
            }
        return {
            **state,
            "final_answer": summary.answer,
            "status": "SUCCESS",
        }

    def after_guardrail(state: AgentState) -> str:
        if state.get("status") == "API_ERROR":
            return END
        return "retrieve_schema" if state["guardrail_allowed"] else END

    def after_generation(state: AgentState) -> str:
        return END if state.get("status") == "API_ERROR" else "validate_sql"

    def after_validation(state: AgentState) -> str:
        if state["validation_result"]["is_valid"]:
            return "execute_sql"
        if state.get("sql_retry_count", 0) >= services.max_sql_repair_attempts:
            return END
        return "repair_sql"

    def after_execution(state: AgentState) -> str:
        if state.get("db_error"):
            if state.get("sql_retry_count", 0) >= services.max_sql_repair_attempts:
                return END
            return "repair_sql"
        return "summarize"

    def after_repair(state: AgentState) -> str:
        return END if state.get("status") == "API_ERROR" else "validate_sql"

    graph.add_node("guardrail", guardrail_node)
    graph.add_node("retrieve_schema", retrieval_node)
    graph.add_node("generate_sql", generate_sql_node)
    graph.add_node("validate_sql", validate_sql_node)
    graph.add_node("execute_sql", execute_sql_node)
    graph.add_node("repair_sql", repair_sql_node)
    graph.add_node("summarize", summarize_node)

    graph.set_entry_point("guardrail")
    graph.add_conditional_edges("guardrail", after_guardrail)
    graph.add_edge("retrieve_schema", "generate_sql")
    graph.add_conditional_edges("generate_sql", after_generation)
    graph.add_conditional_edges("validate_sql", after_validation)
    graph.add_conditional_edges("execute_sql", after_execution)
    graph.add_conditional_edges("repair_sql", after_repair)
    graph.add_edge("summarize", END)
    return graph.compile()


def initial_state(question: str) -> AgentState:
    return {
        "run_id": str(uuid.uuid4()),
        "user_question": question,
        "resolved_question": question,
        "is_follow_up": False,
        "follow_up_reason": "",
        "sql_retry_count": 0,
        "retry_history": [],
        "status": "STARTED",
    }

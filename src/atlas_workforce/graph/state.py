from __future__ import annotations

from typing import Any, Optional, TypedDict


class AgentState(TypedDict, total=False):
    run_id: str
    user_question: str
    resolved_question: str
    is_follow_up: bool
    follow_up_reason: str

    guardrail_allowed: bool
    guardrail_reason: str

    business_context: str
    retrieved_context: str
    retrieved_candidates: list[dict[str, Any]]
    retrieved_tables: list[str]
    retrieval_scores: dict[str, float]
    reranker_scores: dict[str, Optional[float]]

    generated_sql: str
    llm_reported_tables: list[str]

    validation_result: dict[str, Any]
    validated_tables: list[str]

    db_result: dict[str, Any]
    db_error: Optional[str]
    result_truncated: bool

    sql_retry_count: int
    retry_history: list[str]

    final_answer: str
    status: str

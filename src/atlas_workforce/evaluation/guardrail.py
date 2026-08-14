from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atlas_workforce.llm.service import LLMService


@dataclass(frozen=True)
class GuardrailCase:
    id: str
    question: str
    expected_allowed: bool
    category: str


def load_guardrail_cases(path: Path) -> list[GuardrailCase]:
    with path.open("r", encoding="utf-8") as handle:
        raw_cases = json.load(handle)
    return [GuardrailCase(**case) for case in raw_cases]


def evaluate_guardrail_cases(
    cases: list[GuardrailCase],
    llm: LLMService,
    database_scope: str,
) -> dict[str, Any]:
    results = []
    correct = 0
    for case in cases:
        error = None
        allowed = None
        reason = None
        try:
            result = llm.guardrail(case.question, database_scope)
            allowed = result.allowed
            reason = result.reason
            correct += int(allowed == case.expected_allowed)
        except Exception as exc:
            error = str(exc)
        results.append(
            {
                "id": case.id,
                "question": case.question,
                "category": case.category,
                "expected_allowed": case.expected_allowed,
                "actual_allowed": allowed,
                "correct": allowed == case.expected_allowed,
                "reason": reason,
                "error": error,
            }
        )

    total = len(cases)
    return {
        "summary": {
            "total_cases": total,
            "guardrail_accuracy": correct / total if total else 0,
        },
        "cases": results,
    }

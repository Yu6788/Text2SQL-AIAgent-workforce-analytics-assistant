from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from atlas_workforce.llm.service import StubLLMService  # noqa: E402


def test_stub_summary_for_business_unit_headcount_is_natural() -> None:
    summary = StubLLMService().summarize(
        question="How many active employees are in each business unit?",
        sql="SELECT ...",
        columns=["business_unit", "active_headcount"],
        rows=[("Finance", 722), ("People", 697), ("Sales", 679)],
        truncated=False,
    )

    assert "Finance has the highest active headcount" in summary.answer
    assert "followed by People" in summary.answer
    assert "business_unit:" not in summary.answer


def test_stub_summary_for_review_completion_rate_is_percentage() -> None:
    summary = StubLLMService().summarize(
        question="What was the 2026 H1 talent review completion rate?",
        sql="SELECT ...",
        columns=["review_completion_rate"],
        rows=[(0.9421797004991681,)],
        truncated=False,
    )

    assert summary.answer == "The talent review completion rate was 94.2%."


def test_stub_summary_for_program_completion_rate_is_natural() -> None:
    summary = StubLLMService().summarize(
        question="Which development program had the highest completion rate?",
        sql="SELECT ...",
        columns=["program_name", "program_type", "completion_rate_pct"],
        rows=[("Leadership Development 01", "Leadership Development", 87.5)],
        truncated=False,
    )

    assert summary.answer == "Leadership Development 01 had the highest program completion rate at 87.5%."


def test_stub_follow_up_resolver_filters_business_unit() -> None:
    result = StubLLMService().resolve_follow_up(
        question="What about only Technology?",
        previous_question="How many active employees are in each business unit?",
        previous_sql="SELECT ...",
        previous_answer="Finance has the highest active headcount...",
    )

    assert result.is_follow_up
    assert result.resolved_question == "How many active employees are in the Technology business unit?"

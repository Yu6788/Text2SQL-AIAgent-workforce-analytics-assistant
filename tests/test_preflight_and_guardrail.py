from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from atlas_workforce.config.settings import load_settings  # noqa: E402
from atlas_workforce.evaluation.guardrail import evaluate_guardrail_cases, load_guardrail_cases  # noqa: E402
from atlas_workforce.llm.service import StubLLMService  # noqa: E402
from atlas_workforce.preflight import run_preflight  # noqa: E402


DATABASE_SCOPE = (
    "Atlas Workforce analytics tables: employees, organizations, talent_reviews, "
    "development_programs, employee_programs, internal_moves."
)


def test_preflight_passes_current_workspace() -> None:
    settings = load_settings(ROOT / "config.yaml")
    checks = run_preflight(settings, ROOT, ROOT / ".env")

    assert checks
    assert all(check.passed for check in checks)


def test_guardrail_seed_evaluation_with_stub() -> None:
    cases = load_guardrail_cases(ROOT / "evaluation" / "guardrail_questions_seed.json")
    report = evaluate_guardrail_cases(cases, StubLLMService(), DATABASE_SCOPE)

    assert report["summary"]["total_cases"] == 10
    assert report["summary"]["guardrail_accuracy"] >= 0.8

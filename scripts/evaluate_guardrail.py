from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from atlas_workforce.config.settings import load_settings  # noqa: E402
from atlas_workforce.evaluation.guardrail import evaluate_guardrail_cases, load_guardrail_cases  # noqa: E402
from atlas_workforce.llm.factory import create_llm_service  # noqa: E402
from atlas_workforce.llm.service import StubLLMService  # noqa: E402


DATABASE_SCOPE = (
    "Atlas Workforce analytics tables: employees, organizations, talent_reviews, "
    "development_programs, employee_programs, internal_moves."
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate guardrail classification.")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation" / "guardrail_questions_seed.json")
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--llm-provider", choices=["stub", "configured"], default="stub")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    settings = load_settings(args.config)
    if args.llm_provider == "stub":
        llm = StubLLMService()
    else:
        llm = create_llm_service(
            provider=settings.llm.provider,
            model=settings.llm.model,
            base_url=settings.llm.base_url,
            request_timeout_seconds=settings.api.request_timeout_seconds,
            structured_output_retries=settings.structured_output.max_retries,
            env_path=str(args.env),
        )

    report = evaluate_guardrail_cases(
        load_guardrail_cases(args.questions),
        llm,
        DATABASE_SCOPE,
    )
    print(json.dumps(report["summary"], indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote detailed report to {args.output}")


if __name__ == "__main__":
    main()

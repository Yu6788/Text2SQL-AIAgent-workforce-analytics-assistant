from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from atlas_workforce.config.settings import load_settings  # noqa: E402
from atlas_workforce.runtime import RuntimeOptions, run_question  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local stub Text-to-SQL workflow.")
    parser.add_argument("question")
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    args = parser.parse_args()

    settings = load_settings(args.config)
    final_state = run_question(
        settings,
        ROOT,
        args.question,
        RuntimeOptions(llm_provider="stub", embedding_backend="hashing", reranker_backend="lexical"),
    )

    print(f"status: {final_state['status']}")
    print(f"guardrail: {final_state.get('guardrail_allowed')} ({final_state.get('guardrail_reason')})")
    if final_state.get("retrieved_tables"):
        print("\nretrieved_tables:")
        for idx, table in enumerate(final_state["retrieved_tables"], start=1):
            print(f"{idx}. {table}")
    if final_state.get("generated_sql"):
        print("\nsql:")
        print(final_state["generated_sql"])
    if final_state.get("db_result"):
        print("\ncolumns:", final_state["db_result"]["columns"])
        print("rows:", final_state["db_result"]["rows"][:5])
    if final_state.get("final_answer"):
        print("\nanswer:")
        print(final_state["final_answer"])


if __name__ == "__main__":
    main()

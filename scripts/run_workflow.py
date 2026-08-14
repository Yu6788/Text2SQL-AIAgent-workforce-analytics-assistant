from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from atlas_workforce.config.settings import load_settings  # noqa: E402
from atlas_workforce.runtime import RuntimeOptions, build_workflow_services, run_question  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Text-to-SQL workflow.")
    parser.add_argument("question")
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--skip-retrieval", action="store_true")
    parser.add_argument("--embedding-backend", choices=["sentence-transformers", "hashing"], default="sentence-transformers")
    parser.add_argument("--reranker-backend", choices=["cross-encoder", "lexical", "none"], default="cross-encoder")
    args = parser.parse_args()

    settings = load_settings(args.config)
    options = RuntimeOptions(
        llm_provider="configured",
        embedding_backend=args.embedding_backend,
        reranker_backend=args.reranker_backend,
        skip_retrieval=args.skip_retrieval,
        env_path=args.env,
    )
    services = build_workflow_services(settings, ROOT, options)
    final_state = run_question(settings, ROOT, args.question, options)

    print(f"provider: {services.llm.provider_name}")
    print(f"model: {services.llm.model_name}")
    print(f"status: {final_state['status']}")
    print(f"guardrail: {final_state.get('guardrail_allowed')} ({final_state.get('guardrail_reason')})")
    if final_state.get("retrieved_tables"):
        print("\nretrieved_tables:")
        for idx, table in enumerate(final_state["retrieved_tables"], start=1):
            retrieval_score = final_state.get("retrieval_scores", {}).get(table)
            reranker_score = final_state.get("reranker_scores", {}).get(table)
            retrieval_display = "n/a" if retrieval_score is None else f"{retrieval_score:.4f}"
            reranker_display = "n/a" if reranker_score is None else f"{reranker_score:.4f}"
            print(f"{idx}. {table} retrieval={retrieval_display} reranker={reranker_display}")
    if final_state.get("generated_sql"):
        print("\nsql:")
        print(final_state["generated_sql"])
    if final_state.get("validation_result"):
        print("\nvalidation:")
        print(final_state["validation_result"])
    if final_state.get("db_result"):
        print("\ncolumns:", final_state["db_result"]["columns"])
        print("rows:", final_state["db_result"]["rows"][:5])
    if final_state.get("db_error"):
        print("\ndb_error:")
        print(final_state["db_error"])
    if final_state.get("final_answer"):
        print("\nanswer:")
        print(final_state["final_answer"])


if __name__ == "__main__":
    main()

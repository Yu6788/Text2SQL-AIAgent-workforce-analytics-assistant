from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from atlas_workforce.config.settings import load_settings  # noqa: E402
from atlas_workforce.evaluation.runner import evaluate_cases, load_cases  # noqa: E402
from atlas_workforce.graph.workflow import WorkflowServices  # noqa: E402
from atlas_workforce.llm.factory import create_llm_service  # noqa: E402
from atlas_workforce.llm.service import StubLLMService  # noqa: E402
from atlas_workforce.rag.documents import build_table_documents  # noqa: E402
from atlas_workforce.rag.embeddings import HashingEmbedder, create_embedder  # noqa: E402
from atlas_workforce.rag.reranker import LexicalReranker, create_reranker  # noqa: E402
from atlas_workforce.rag.retrieval import build_in_memory_store  # noqa: E402
from atlas_workforce.rag.vector_store import load_vector_store  # noqa: E402
from atlas_workforce.sql.executor import DuckDBExecutor  # noqa: E402
from atlas_workforce.sql.validator import SQLValidator  # noqa: E402


def load_business_context(path: Path) -> str:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_dump(yaml.safe_load(handle), sort_keys=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Text-to-SQL execution accuracy.")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation" / "questions_seed.json")
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--llm-provider", choices=["stub", "configured"], default="stub")
    parser.add_argument("--embedding-backend", choices=["hashing", "sentence-transformers"], default="hashing")
    parser.add_argument("--reranker-backend", choices=["lexical", "cross-encoder", "none"], default="lexical")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    settings = load_settings(args.config)
    documents = build_table_documents(ROOT / "metadata")

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

    if args.embedding_backend == "hashing":
        embedder = HashingEmbedder()
        vector_store = build_in_memory_store(ROOT / "metadata", embedder)
    else:
        embedder = create_embedder(
            "sentence-transformers",
            model_name=settings.rag.embedding_model,
            device="cpu",
        )
        vector_store = load_vector_store(settings.vector_store.index_path)

    reranker = None
    if args.reranker_backend == "lexical":
        reranker = LexicalReranker()
    elif args.reranker_backend == "cross-encoder":
        reranker = create_reranker(
            "cross-encoder",
            model_name=settings.rag.reranker_model,
            device="cpu",
        )

    executor = DuckDBExecutor(
        database_path=settings.database.path,
        read_only=True,
        max_result_rows=settings.database.max_result_rows,
    )
    services = WorkflowServices(
        llm=llm,
        validator=SQLValidator(
            dialect=settings.sql.dialect,
            allow_cross_join=settings.sql.allow_cross_join,
        ),
        executor=executor,
        business_context=load_business_context(ROOT / "metadata" / "business_context.yaml"),
        schema_context="\n\n".join(document.text for document in documents),
        embedder=embedder,
        vector_store=vector_store,
        reranker=reranker,
        retrieval_top_k=settings.rag.retrieval_top_k,
        rerank_top_k=settings.rag.rerank_top_k,
        max_sql_repair_attempts=settings.sql.max_repair_attempts,
    )

    report = evaluate_cases(load_cases(args.questions), services, executor)
    print(json.dumps(report["summary"], indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote detailed report to {args.output}")


if __name__ == "__main__":
    main()

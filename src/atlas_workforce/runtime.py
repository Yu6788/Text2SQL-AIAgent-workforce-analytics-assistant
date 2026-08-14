from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from atlas_workforce.config.settings import Settings
from atlas_workforce.graph.workflow import WorkflowServices, create_workflow, initial_state
from atlas_workforce.llm.factory import create_llm_service
from atlas_workforce.llm.service import StubLLMService
from atlas_workforce.rag.documents import build_table_documents
from atlas_workforce.rag.embeddings import HashingEmbedder, create_embedder
from atlas_workforce.rag.reranker import LexicalReranker, create_reranker
from atlas_workforce.rag.retrieval import build_in_memory_store
from atlas_workforce.rag.vector_store import load_vector_store
from atlas_workforce.sql.executor import DuckDBExecutor
from atlas_workforce.sql.validator import SQLValidator


@dataclass(frozen=True)
class RuntimeOptions:
    llm_provider: str = "stub"
    embedding_backend: str = "hashing"
    reranker_backend: str = "lexical"
    skip_retrieval: bool = False
    env_path: Path = Path(".env")


def load_business_context(path: Path) -> str:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_dump(yaml.safe_load(handle), sort_keys=False)


def build_workflow_services(settings: Settings, root: Path, options: RuntimeOptions) -> WorkflowServices:
    documents = build_table_documents(root / "metadata")

    if options.llm_provider == "stub":
        llm = StubLLMService()
    else:
        llm = create_llm_service(
            provider=settings.llm.provider,
            model=settings.llm.model,
            base_url=settings.llm.base_url,
            request_timeout_seconds=settings.api.request_timeout_seconds,
            structured_output_retries=settings.structured_output.max_retries,
            env_path=str(options.env_path),
        )

    embedder = None
    vector_store = None
    reranker = None
    if not options.skip_retrieval:
        if options.embedding_backend == "hashing":
            embedder = HashingEmbedder()
            vector_store = build_in_memory_store(root / "metadata", embedder)
        else:
            embedder = create_embedder(
                "sentence-transformers",
                model_name=settings.rag.embedding_model,
                device="cpu",
            )
            vector_store = load_vector_store(settings.vector_store.index_path)

        if options.reranker_backend == "lexical":
            reranker = LexicalReranker()
        elif options.reranker_backend == "cross-encoder":
            reranker = create_reranker(
                "cross-encoder",
                model_name=settings.rag.reranker_model,
                device="cpu",
            )

    return WorkflowServices(
        llm=llm,
        validator=SQLValidator(
            dialect=settings.sql.dialect,
            allow_cross_join=settings.sql.allow_cross_join,
        ),
        executor=DuckDBExecutor(
            database_path=settings.database.path,
            read_only=settings.database.read_only,
            max_result_rows=settings.database.max_result_rows,
            query_timeout_seconds=settings.database.query_timeout_seconds,
        ),
        business_context=load_business_context(root / "metadata" / "business_context.yaml"),
        schema_context="\n\n".join(document.text for document in documents),
        embedder=embedder,
        vector_store=vector_store,
        reranker=reranker,
        retrieval_top_k=settings.rag.retrieval_top_k,
        rerank_top_k=settings.rag.rerank_top_k,
        max_sql_repair_attempts=settings.sql.max_repair_attempts,
    )


def run_question(
    settings: Settings,
    root: Path,
    question: str,
    options: RuntimeOptions,
    previous_state: Optional[dict] = None,
    force_follow_up: bool = False,
) -> dict:
    services = build_workflow_services(settings, root, options)
    app = create_workflow(services)
    state = initial_state(question)
    if force_follow_up or previous_state:
        resolution = services.llm.resolve_follow_up(
            question=question,
            previous_question=previous_state.get("user_question") if previous_state else None,
            previous_sql=previous_state.get("generated_sql") if previous_state else None,
            previous_answer=previous_state.get("final_answer") if previous_state else None,
        )
        state["resolved_question"] = resolution.resolved_question
        state["is_follow_up"] = resolution.is_follow_up
        state["follow_up_reason"] = resolution.reason
    return app.invoke(state)

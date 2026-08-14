from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from atlas_workforce.rag.documents import TableDocument, build_table_documents
from atlas_workforce.rag.embeddings import Embedder
from atlas_workforce.rag.reranker import Reranker
from atlas_workforce.rag.vector_store import NumpyVectorStore, load_vector_store


@dataclass(frozen=True)
class RetrievedTable:
    table_name: str
    retrieval_score: float
    reranker_score: float | None
    document: str


def build_in_memory_store(metadata_dir: Path, embedder: Embedder) -> NumpyVectorStore:
    documents = build_table_documents(metadata_dir)
    embeddings = embedder.encode_documents([document.text for document in documents])
    return NumpyVectorStore(embeddings, documents)


def retrieve_tables(
    question: str,
    embedder: Embedder,
    store: NumpyVectorStore,
    retrieval_top_k: int = 20,
    rerank_top_k: int = 4,
    reranker: Reranker | None = None,
) -> list[RetrievedTable]:
    query_embedding = embedder.encode_query(question)
    candidates = store.search(query_embedding, retrieval_top_k)
    retrieval_score_by_table = {
        document.table_name: score for document, score in candidates
    }

    if reranker is None:
        selected = candidates[: min(rerank_top_k, len(candidates))]
        return [
            RetrievedTable(
                table_name=document.table_name,
                retrieval_score=score,
                reranker_score=None,
                document=document.text,
            )
            for document, score in selected
        ]

    reranked = reranker.rerank(question, candidates, rerank_top_k)
    return [
        RetrievedTable(
            table_name=document.table_name,
            retrieval_score=retrieval_score_by_table[document.table_name],
            reranker_score=score,
            document=document.text,
        )
        for document, score in reranked
    ]


def retrieve_from_index(
    question: str,
    embedder: Embedder,
    index_dir: Path,
    retrieval_top_k: int = 20,
    rerank_top_k: int = 4,
    reranker: Reranker | None = None,
) -> list[RetrievedTable]:
    store = load_vector_store(index_dir)
    return retrieve_tables(
        question=question,
        embedder=embedder,
        store=store,
        retrieval_top_k=retrieval_top_k,
        rerank_top_k=rerank_top_k,
        reranker=reranker,
    )

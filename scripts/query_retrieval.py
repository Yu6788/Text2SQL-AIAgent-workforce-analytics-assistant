from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from atlas_workforce.rag.embeddings import create_embedder  # noqa: E402
from atlas_workforce.rag.reranker import create_reranker  # noqa: E402
from atlas_workforce.rag.retrieval import retrieve_from_index  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the schema retrieval index.")
    parser.add_argument("question")
    parser.add_argument("--index-dir", type=Path, default=ROOT / "data" / "faiss_index")
    parser.add_argument(
        "--embedding-backend",
        choices=["sentence-transformers", "hashing"],
        default="sentence-transformers",
    )
    parser.add_argument("--embedding-model", default="BAAI/bge-small-en-v1.5")
    parser.add_argument("--reranker-backend", choices=["cross-encoder", "lexical", "none"], default="cross-encoder")
    parser.add_argument("--reranker-model", default="cross-encoder/ms-marco-MiniLM-L6-v2")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--retrieval-top-k", type=int, default=20)
    parser.add_argument("--rerank-top-k", type=int, default=4)
    args = parser.parse_args()

    embedder_kwargs: dict[str, object] = {}
    if args.embedding_backend == "sentence-transformers":
        embedder_kwargs = {"model_name": args.embedding_model, "device": args.device}
    embedder = create_embedder(args.embedding_backend, **embedder_kwargs)

    reranker = None
    if args.reranker_backend != "none":
        reranker_kwargs: dict[str, object] = {}
        if args.reranker_backend == "cross-encoder":
            reranker_kwargs = {"model_name": args.reranker_model, "device": args.device}
        reranker = create_reranker(args.reranker_backend, **reranker_kwargs)

    results = retrieve_from_index(
        question=args.question,
        embedder=embedder,
        index_dir=args.index_dir,
        retrieval_top_k=args.retrieval_top_k,
        rerank_top_k=args.rerank_top_k,
        reranker=reranker,
    )

    for rank, result in enumerate(results, start=1):
        reranker_score = "n/a" if result.reranker_score is None else f"{result.reranker_score:.4f}"
        print(
            f"{rank}. {result.table_name} "
            f"(retrieval={result.retrieval_score:.4f}, reranker={reranker_score})"
        )


if __name__ == "__main__":
    main()

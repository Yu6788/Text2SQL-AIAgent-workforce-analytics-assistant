from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from atlas_workforce.rag.embeddings import create_embedder  # noqa: E402
from atlas_workforce.rag.reranker import create_reranker  # noqa: E402
from atlas_workforce.rag.retrieval import retrieve_from_index  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate schema retrieval recall.")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation" / "retrieval_smoke_questions.json")
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

    with args.questions.open("r", encoding="utf-8") as handle:
        cases = json.load(handle)

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

    recalls = []
    all_required_hits = 0
    for case in cases:
        results = retrieve_from_index(
            question=case["question"],
            embedder=embedder,
            index_dir=args.index_dir,
            retrieval_top_k=args.retrieval_top_k,
            rerank_top_k=args.rerank_top_k,
            reranker=reranker,
        )
        retrieved = [result.table_name for result in results]
        expected = set(case["expected_tables"])
        hits = len(expected & set(retrieved))
        recall = hits / len(expected)
        recalls.append(recall)
        all_required_hits += int(hits == len(expected))
        print(f"{case['id']}: recall@{args.rerank_top_k}={recall:.2f} retrieved={retrieved}")

    avg_recall = sum(recalls) / len(recalls)
    all_required = all_required_hits / len(cases)
    print(f"\nAverage Table Recall@{args.rerank_top_k}: {avg_recall:.3f}")
    print(f"All-Required-Tables Recall@{args.rerank_top_k}: {all_required:.3f}")


if __name__ == "__main__":
    main()

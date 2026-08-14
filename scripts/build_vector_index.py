from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from atlas_workforce.rag.documents import build_table_documents  # noqa: E402
from atlas_workforce.rag.embeddings import create_embedder  # noqa: E402
from atlas_workforce.rag.vector_store import create_vector_store  # noqa: E402


def build_index(
    metadata_dir: Path,
    index_dir: Path,
    embedding_backend: str,
    vector_backend: str,
    embedding_model: str,
    device: str,
) -> None:
    documents = build_table_documents(metadata_dir)
    embedder_kwargs: dict[str, object] = {}
    if embedding_backend == "sentence-transformers":
        embedder_kwargs = {"model_name": embedding_model, "device": device}
    embedder = create_embedder(embedding_backend, **embedder_kwargs)
    embeddings = embedder.encode_documents([document.text for document in documents])
    store = create_vector_store(vector_backend, embeddings, documents)
    index_dir.mkdir(parents=True, exist_ok=True)
    for stale_file in ["index.faiss", "embeddings.npy", "documents.json", "backend.txt"]:
        path = index_dir / stale_file
        if path.exists():
            path.unlink()
    store.save(index_dir)

    print(f"Indexed {len(documents)} table metadata documents")
    print(f"Embedding backend: {embedding_backend}")
    print(f"Vector backend: {vector_backend}")
    print(f"Index path: {index_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the schema vector index.")
    parser.add_argument("--metadata-dir", type=Path, default=ROOT / "metadata")
    parser.add_argument("--index-dir", type=Path, default=ROOT / "data" / "faiss_index")
    parser.add_argument(
        "--embedding-backend",
        choices=["sentence-transformers", "hashing"],
        default="sentence-transformers",
    )
    parser.add_argument(
        "--vector-backend",
        choices=["faiss", "numpy"],
        default="faiss",
    )
    parser.add_argument("--embedding-model", default="BAAI/bge-small-en-v1.5")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    build_index(
        metadata_dir=args.metadata_dir,
        index_dir=args.index_dir,
        embedding_backend=args.embedding_backend,
        vector_backend=args.vector_backend,
        embedding_model=args.embedding_model,
        device=args.device,
    )


if __name__ == "__main__":
    main()

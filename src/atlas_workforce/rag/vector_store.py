from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from atlas_workforce.rag.documents import TableDocument


class NumpyVectorStore:
    def __init__(self, embeddings: np.ndarray, documents: list[TableDocument]) -> None:
        if len(embeddings) != len(documents):
            raise ValueError("Embedding/document count mismatch")
        self.embeddings = embeddings.astype("float32")
        self.documents = documents

    def search(self, query_embedding: np.ndarray, top_k: int) -> list[tuple[TableDocument, float]]:
        query = query_embedding.reshape(1, -1).astype("float32")
        scores = (self.embeddings @ query.T).reshape(-1)
        order = np.argsort(-scores)[: min(top_k, len(self.documents))]
        return [(self.documents[int(idx)], float(scores[int(idx)])) for idx in order]

    def save(self, index_dir: Path) -> None:
        index_dir.mkdir(parents=True, exist_ok=True)
        np.save(index_dir / "embeddings.npy", self.embeddings)
        with (index_dir / "documents.json").open("w", encoding="utf-8") as handle:
            json.dump([asdict(document) for document in self.documents], handle, indent=2, default=str)
        (index_dir / "backend.txt").write_text("numpy\n", encoding="utf-8")

    @classmethod
    def load(cls, index_dir: Path) -> "NumpyVectorStore":
        embeddings = np.load(index_dir / "embeddings.npy")
        with (index_dir / "documents.json").open("r", encoding="utf-8") as handle:
            raw_documents = json.load(handle)
        documents = [TableDocument(**record) for record in raw_documents]
        return cls(embeddings, documents)


class FaissVectorStore:
    def __init__(self, embeddings: np.ndarray, documents: list[TableDocument]) -> None:
        try:
            import faiss
        except ImportError as exc:
            raise ImportError(
                "faiss-cpu is required for the FAISS vector store. "
                "Install dependencies with: python3 -m pip install -r requirements.txt"
            ) from exc

        if len(embeddings) != len(documents):
            raise ValueError("Embedding/document count mismatch")
        self.faiss = faiss
        self.documents = documents
        self.index = faiss.IndexFlatIP(int(embeddings.shape[1]))
        self.index.add(embeddings.astype("float32"))

    def search(self, query_embedding: np.ndarray, top_k: int) -> list[tuple[TableDocument, float]]:
        k = min(top_k, len(self.documents))
        scores, indices = self.index.search(query_embedding.reshape(1, -1).astype("float32"), k)
        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx < 0:
                continue
            results.append((self.documents[int(idx)], float(score)))
        return results

    def save(self, index_dir: Path) -> None:
        index_dir.mkdir(parents=True, exist_ok=True)
        self.faiss.write_index(self.index, str(index_dir / "index.faiss"))
        with (index_dir / "documents.json").open("w", encoding="utf-8") as handle:
            json.dump([asdict(document) for document in self.documents], handle, indent=2, default=str)
        (index_dir / "backend.txt").write_text("faiss\n", encoding="utf-8")

    @classmethod
    def load(cls, index_dir: Path) -> "FaissVectorStore":
        try:
            import faiss
        except ImportError as exc:
            raise ImportError(
                "faiss-cpu is required to load a FAISS index. "
                "Install dependencies with: python3 -m pip install -r requirements.txt"
            ) from exc

        with (index_dir / "documents.json").open("r", encoding="utf-8") as handle:
            raw_documents = json.load(handle)
        documents = [TableDocument(**record) for record in raw_documents]
        store = cls.__new__(cls)
        store.faiss = faiss
        store.documents = documents
        store.index = faiss.read_index(str(index_dir / "index.faiss"))
        return store


def create_vector_store(
    backend: str,
    embeddings: np.ndarray,
    documents: list[TableDocument],
) -> NumpyVectorStore | FaissVectorStore:
    if backend == "numpy":
        return NumpyVectorStore(embeddings, documents)
    if backend == "faiss":
        return FaissVectorStore(embeddings, documents)
    raise ValueError(f"Unknown vector store backend: {backend}")


def load_vector_store(index_dir: Path) -> NumpyVectorStore | FaissVectorStore:
    backend = (index_dir / "backend.txt").read_text(encoding="utf-8").strip()
    if backend == "numpy":
        return NumpyVectorStore.load(index_dir)
    if backend == "faiss":
        return FaissVectorStore.load(index_dir)
    raise ValueError(f"Unknown stored vector backend: {backend}")

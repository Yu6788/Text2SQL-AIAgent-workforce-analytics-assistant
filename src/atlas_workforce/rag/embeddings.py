from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    dimension: int

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        ...

    def encode_query(self, text: str) -> np.ndarray:
        ...


def normalize_rows(matrix: np.ndarray) -> np.ndarray:
    matrix = matrix.astype("float32", copy=False)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


@dataclass
class HashingEmbedder:
    dimension: int = 384
    query_prefix: str = "Represent this sentence for searching relevant passages: "

    def _encode(self, texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dimension), dtype="float32")
        for row_idx, text in enumerate(texts):
            tokens = re.findall(r"[a-z0-9_]+", text.lower())
            for token in tokens:
                digest = hashlib.md5(token.encode("utf-8")).hexdigest()
                index = int(digest[:8], 16) % self.dimension
                sign = 1.0 if int(digest[8:10], 16) % 2 == 0 else -1.0
                matrix[row_idx, index] += sign
            if tokens:
                matrix[row_idx] /= math.sqrt(len(tokens))
        return normalize_rows(matrix)

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        return self._encode(texts)

    def encode_query(self, text: str) -> np.ndarray:
        return self._encode([self.query_prefix + text])


class SentenceTransformerEmbedder:
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        device: str = "cpu",
        normalize_embeddings: bool = True,
        query_prefix: str = "Represent this sentence for searching relevant passages: ",
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is required for the production embedding backend. "
                "Install dependencies with: python3 -m pip install -r requirements.txt"
            ) from exc

        self.model = SentenceTransformer(model_name, device=device)
        self.dimension = int(self.model.get_sentence_embedding_dimension())
        self.normalize_embeddings = normalize_embeddings
        self.query_prefix = query_prefix

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
        )
        return vectors.astype("float32")

    def encode_query(self, text: str) -> np.ndarray:
        vectors = self.model.encode(
            [self.query_prefix + text],
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
        )
        return vectors.astype("float32")


def create_embedder(backend: str = "sentence-transformers", **kwargs: object) -> Embedder:
    if backend == "hashing":
        return HashingEmbedder(**kwargs)
    if backend == "sentence-transformers":
        return SentenceTransformerEmbedder(**kwargs)
    raise ValueError(f"Unknown embedding backend: {backend}")

from __future__ import annotations

import re
from dataclasses import dataclass
import math
from typing import Protocol

from atlas_workforce.rag.documents import TableDocument


class Reranker(Protocol):
    def rerank(
        self,
        question: str,
        candidates: list[tuple[TableDocument, float]],
        top_k: int,
    ) -> list[tuple[TableDocument, float]]:
        ...


@dataclass
class LexicalReranker:
    """Small deterministic reranker for tests and offline smoke checks."""

    table_aliases = {
        "employees": {"employee", "employees", "workforce", "headcount", "active"},
        "organizations": {"organization", "organizations", "org", "business", "unit", "region"},
        "talent_reviews": {"review", "reviews", "talent", "performance", "rating", "promotion", "recommended"},
        "development_programs": {"development", "program", "programs", "leadership", "mentorship", "training"},
        "employee_programs": {"enrollment", "enrollments", "completed", "completion", "program", "programs", "leadership"},
        "internal_moves": {"move", "moves", "mobility", "promotion", "promoted", "transfer", "later"},
    }

    def rerank(
        self,
        question: str,
        candidates: list[tuple[TableDocument, float]],
        top_k: int,
    ) -> list[tuple[TableDocument, float]]:
        question_terms = set(re.findall(r"[a-z0-9_]+", question.lower()))
        scored = []
        for document, base_score in candidates:
            doc_terms = set(re.findall(r"[a-z0-9_]+", document.text.lower()))
            overlap = len(question_terms & doc_terms)
            alias_overlap = len(question_terms & self.table_aliases.get(document.table_name, set()))
            explicit_table_boost = 0.0
            if document.table_name == "employees" and {"employee", "employees"} & question_terms:
                explicit_table_boost = 6.0
            if (
                document.table_name == "employees"
                and {"business", "unit"} <= question_terms
                and {"performance", "rating", "review", "talent"} & question_terms
            ):
                explicit_table_boost += 5.0
            scored.append(
                (
                    document,
                    float(overlap) + alias_overlap * 2.0 + explicit_table_boost + base_score * 0.01,
                )
            )
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[: min(top_k, len(scored))]


class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L6-v2",
        device: str = "cpu",
    ) -> None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is required for the CrossEncoder reranker. "
                "Install dependencies with: python3 -m pip install -r requirements.txt"
            ) from exc
        self.model = CrossEncoder(model_name, device=device)

    def rerank(
        self,
        question: str,
        candidates: list[tuple[TableDocument, float]],
        top_k: int,
    ) -> list[tuple[TableDocument, float]]:
        pairs = [(question, document.text) for document, _ in candidates]
        scores = self.model.predict(pairs)
        if any(not math.isfinite(float(score)) for score in scores):
            return LexicalReranker().rerank(question, candidates, top_k)
        scored = [
            (document, float(score))
            for (document, _), score in zip(candidates, scores)
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[: min(top_k, len(scored))]


def create_reranker(backend: str = "cross-encoder", **kwargs: object) -> Reranker:
    if backend == "lexical":
        return LexicalReranker(**kwargs)
    if backend == "cross-encoder":
        return CrossEncoderReranker(**kwargs)
    raise ValueError(f"Unknown reranker backend: {backend}")

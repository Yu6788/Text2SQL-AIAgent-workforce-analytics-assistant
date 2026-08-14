from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from atlas_workforce.rag.documents import build_table_documents  # noqa: E402
from atlas_workforce.rag.embeddings import HashingEmbedder  # noqa: E402
from atlas_workforce.rag.reranker import CrossEncoderReranker, LexicalReranker  # noqa: E402
from atlas_workforce.rag.retrieval import retrieve_from_index, retrieve_tables  # noqa: E402
from atlas_workforce.rag.vector_store import NumpyVectorStore  # noqa: E402
from build_vector_index import build_index  # noqa: E402


def test_metadata_documents_are_serialized() -> None:
    documents = build_table_documents(ROOT / "metadata")

    assert len(documents) == 6
    table_names = {document.table_name for document in documents}
    assert "employees" in table_names
    assert "talent_reviews" in table_names
    assert all("Columns:" in document.text for document in documents)
    assert all(len(document.text.split()) < 450 for document in documents)


def test_hashing_retrieval_returns_expected_tables() -> None:
    documents = build_table_documents(ROOT / "metadata")
    embedder = HashingEmbedder()
    embeddings = embedder.encode_documents([document.text for document in documents])
    store = NumpyVectorStore(embeddings, documents)

    results = retrieve_tables(
        question="Which development program had the highest completion rate?",
        embedder=embedder,
        store=store,
        reranker=LexicalReranker(),
    )
    retrieved = [result.table_name for result in results]

    assert "development_programs" in retrieved
    assert "employee_programs" in retrieved
    assert len(retrieved) == 4


def test_lexical_reranker_includes_employee_bridge_for_business_unit_reviews() -> None:
    documents = build_table_documents(ROOT / "metadata")
    embedder = HashingEmbedder()
    embeddings = embedder.encode_documents([document.text for document in documents])
    store = NumpyVectorStore(embeddings, documents)

    results = retrieve_tables(
        question="Which business unit had the highest average performance rating in 2026 H1?",
        embedder=embedder,
        store=store,
        reranker=LexicalReranker(),
    )
    retrieved = [result.table_name for result in results]

    assert "talent_reviews" in retrieved
    assert "employees" in retrieved
    assert "organizations" in retrieved


def test_index_save_load_roundtrip(tmp_path: Path) -> None:
    index_dir = tmp_path / "schema_index"
    build_index(
        metadata_dir=ROOT / "metadata",
        index_dir=index_dir,
        embedding_backend="hashing",
        vector_backend="numpy",
        embedding_model="unused",
        device="cpu",
    )

    results = retrieve_from_index(
        question="How many active employees are in each business unit?",
        embedder=HashingEmbedder(),
        index_dir=index_dir,
        reranker=LexicalReranker(),
    )
    retrieved = [result.table_name for result in results]

    assert "employees" in retrieved
    assert "organizations" in retrieved


def test_cross_encoder_reranker_falls_back_on_non_finite_scores() -> None:
    class NanModel:
        def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
            return [float("nan") for _ in pairs]

    documents = build_table_documents(ROOT / "metadata")
    candidates = [(document, 0.1) for document in documents]
    reranker = CrossEncoderReranker.__new__(CrossEncoderReranker)
    reranker.model = NanModel()

    results = reranker.rerank(
        "Did employees who completed Leadership Development programs have a higher later promotion rate?",
        candidates,
        top_k=4,
    )
    retrieved = [document.table_name for document, _ in results]

    assert "employees" in retrieved
    assert "internal_moves" in retrieved

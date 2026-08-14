# Phase 2 Retrieval Verification

## Production Retrieval Command

Build the schema index with BGE embeddings and FAISS:

```bash
python3 scripts/build_vector_index.py \
  --embedding-backend sentence-transformers \
  --vector-backend faiss \
  --index-dir data/faiss_index
```

Observed result:

```text
Indexed 6 table metadata documents
Embedding backend: sentence-transformers
Vector backend: faiss
Index path: data/faiss_index
```

## Retrieval Smoke Evaluation

Run the smoke retrieval evaluation:

```bash
python3 scripts/evaluate_retrieval.py \
  --embedding-backend sentence-transformers \
  --reranker-backend cross-encoder \
  --index-dir data/faiss_index
```

Observed result on the 4-case smoke set:

```text
Average Table Recall@4: 1.000
All-Required-Tables Recall@4: 1.000
```

## CrossEncoder Note

On the current local environment, direct
`cross-encoder/ms-marco-MiniLM-L6-v2` predictions returned `nan`.
The `CrossEncoderReranker` now detects non-finite scores and falls back
to the deterministic lexical reranker instead of silently propagating
invalid scores.

This means the smoke evaluation verifies:

- BGE model loading
- FAISS index construction and search
- CrossEncoder loading path
- non-finite reranker score protection
- Top-4 schema recall on the current smoke cases

It does not prove that CrossEncoder reranking improved retrieval quality
in this environment. The full retrieval ablation should be rerun when the
80-question evaluation set exists and the CrossEncoder produces finite
scores.

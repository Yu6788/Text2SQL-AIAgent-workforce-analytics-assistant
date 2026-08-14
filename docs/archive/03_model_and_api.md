# Atlas Workforce Text-to-SQL — Model, API, Safety, and Observability Specification

## 1. LLM Strategy

The architecture must be **provider-agnostic**.

Do not hard-code the graph to OpenAI, Gemini, OpenRouter, Anthropic, or any other provider.

The exact development and deployment models remain configurable until Phase 3.

Recommended logical design:

```text
LangGraph
    |
    v
LLM Service
    |
    v
Provider Adapter
    |
    +--> provider A
    +--> provider B
    +--> provider C
```

The goal is to allow provider/model changes without rewriting the LangGraph workflow.

---

## 2. LLM Service Interface

Conceptual service:

```python
class LLMService:
    def guardrail(...):
        ...

    def generate_sql(...):
        ...

    def repair_sql(...):
        ...

    def summarize(...):
        ...
```

Nodes call the service, not provider SDKs directly.

A lower-level generic interface may expose:

```python
generate_structured(
    task,
    messages,
    output_schema
)
```

---

## 3. LLM Model Selection Status

Current decision:

```text
development provider = TBD
development model = TBD

benchmark provider = TBD
benchmark model = TBD

deployment provider = TBD
deployment model = TBD
```

This is intentional.

The project should first complete:

- data foundation
- DuckDB
- metadata
- embedding
- FAISS
- reranking

before committing to a specific paid or free LLM.

Later candidate models should be compared on:

- execution accuracy
- retry rate
- latency
- token usage
- cost

---

## 4. Local Embedding Model

Use:

```text
BAAI/bge-small-en-v1.5
```

Configuration:

```yaml
embedding:
  provider: local
  model: BAAI/bge-small-en-v1.5
  dimension: 384
  normalize_embeddings: true
  device: cpu
```

V1 supports English questions.

For short query -> longer metadata retrieval, apply the model's recommended query instruction/prefix to the query only.

Table documents themselves should remain clean metadata text.

---

## 5. FAISS

Use:

```text
IndexFlatIP
```

Because embeddings are normalized:

```text
inner product ~= cosine similarity ranking
```

Do not add IVF, PQ, HNSW, or GPU FAISS in V1.

The schema is tiny and exact search is appropriate.

---

## 6. Local Reranker

Use:

```text
cross-encoder/ms-marco-MiniLM-L6-v2
```

Configuration:

```yaml
reranker:
  provider: local
  model: cross-encoder/ms-marco-MiniLM-L6-v2
  device: cpu
```

Retrieval pipeline:

```text
Question
  ->
BGE embedding
  ->
FAISS candidate ranking
  ->
CrossEncoder reranking
  ->
Top 4 table metadata documents
```

---

## 7. Retrieval Configuration

```yaml
retrieval:
  retrieval_top_k: 20
  rerank_top_k: 4
```

Runtime:

```python
candidate_k = min(retrieval_top_k, index_size)
```

With six V1 tables, all six are ranked by FAISS and the reranker keeps four.

---

## 8. RAG Chunk Policy

Use:

```text
one table = one retrieval document
```

Target:

```text
approximately <= 450 tokens per table metadata document
```

Do not implement:

- column-level chunks
- parent-child chunks
- domain router
- multiple schema vector stores

in V1.

---

## 9. Structured Output

Every LLM-facing node must return validated structured output.

Do not rely on regex extraction from arbitrary prose.

### Guardrail

```python
class GuardrailResult(BaseModel):
    allowed: bool
    reason: str
```

### SQL Generation

```python
class SQLGenerationResult(BaseModel):
    sql: str
    tables_used: list[str]
```

### SQL Repair

```python
class SQLRepairResult(BaseModel):
    sql: str
```

### Summary

```python
class SummaryResult(BaseModel):
    answer: str
```

If a provider supports native JSON Schema / structured output, use it.

If not:

1. instruct the model to return strict JSON
2. parse
3. validate with Pydantic
4. perform at most the configured structured-output retry

---

## 10. Prompt Contracts

### 10.1 Guardrail Prompt

Input:

```text
database scope summary
+
user question
```

Do not send full table schemas.

The task is:

> determine whether the question is reasonably answerable from the workforce database.

### 10.2 SQL Generation Prompt

Input:

```text
system SQL instructions
+
global business definitions
+
Top-4 reranked table metadata
+
user question
```

Core rules:

- use only supplied tables/columns
- do not invent schema
- use documented relationships
- follow business metric definitions
- generate DuckDB SQL
- one read-only query
- no mutation
- no external data access

### 10.3 SQL Repair Prompt

Input:

```text
original user question
+
business definitions
+
original retrieved schema context
+
previous SQL
+
current validator/database error
+
compact retry history
```

Do not rerun RAG.

### 10.4 Summary Prompt

Input:

```text
original question
+
final SQL
+
database columns
+
database result
+
truncation indicator
```

Output only a concise answer grounded in the result.

---

## 11. Prompt Versioning

Store prompts as versioned files:

```text
src/prompts/
    guardrail_v1.txt
    sql_generation_v1.txt
    sql_repair_v1.txt
    summary_v1.txt
```

Configuration should select versions.

Example:

```yaml
prompts:
  guardrail: guardrail_v1
  sql_generation: sql_generation_v1
  sql_repair: sql_repair_v1
  summary: summary_v1
```

Do not overwrite prompts without versioning if they are used in evaluation.

---

## 12. SQL Safety

Use SQLGlot with DuckDB dialect.

Validation rules:

```yaml
sql_validation:
  parser: sqlglot
  dialect: duckdb
  max_statements: 1
  allow_select: true
  allow_cte: true
  allow_cross_join: false
  whitelist_only: true
  allow_external_access: false
```

Whitelisted tables:

```text
organizations
employees
talent_reviews
development_programs
employee_programs
internal_moves
```

Reject external access patterns such as:

- CSV readers
- Parquet readers
- JSON readers
- glob/file scans
- URL-based table functions
- attach/load/install operations

DuckDB should additionally be opened with read-only access for generated queries.

---

## 13. Retry Types

### 13.1 API / Infrastructure Retry

Applies to:

- timeout
- network error
- 429
- transient 5xx

Recommended:

```yaml
api:
  max_attempts: 3
  request_timeout_seconds: 30
  initial_backoff_seconds: 1
  max_backoff_seconds: 8
```

Use exponential backoff with jitter where practical.

This does not increment SQL retry count.

### 13.2 Structured Output Retry

Applies when the API succeeds but output cannot be validated against the expected schema.

```yaml
structured_output:
  max_retries: 1
```

After failure:

```text
MODEL_OUTPUT_ERROR
```

### 13.3 SQL Repair Retry

Applies after valid model output creates SQL that:

- fails SQL validation
- or fails DuckDB execution

```yaml
sql:
  max_repair_attempts: 3
```

This counter is independent from API and output-format retries.

---

## 14. Database Execution Protection

Configuration:

```yaml
database:
  type: duckdb
  path: data/atlas_workforce.duckdb
  read_only: true
  query_timeout_seconds: 10
  max_result_rows: 200
```

Normal analytical queries over the V1 synthetic dataset should not approach the 10-second limit.

---

## 15. Result Limiting

Use a controlled wrapper around validated SQL to detect result truncation.

Conceptually:

```sql
SELECT *
FROM (
    <validated SQL>
) AS result
LIMIT 201
```

Behavior:

```text
<= 200 rows -> complete
201 rows    -> return first 200 and set truncated=true
```

Do not silently claim the first 200 rows represent the full result set.

---

## 16. Query Complexity Policy

V1 intentionally avoids a complicated cost estimator.

Allow:

- joins
- CTEs
- window functions
- subqueries
- three- and four-table analytical queries

Reject:

- unneeded `CROSS JOIN`

The timeout provides an additional execution guard.

---

## 17. Unified Query Result Contract

Use a stable object such as:

```python
class QueryResult(BaseModel):
    columns: list[str]
    rows: list
    row_count: int
    truncated: bool
    execution_time_ms: float
```

Do not pass raw DuckDB cursors throughout the graph.

---

## 18. Configuration

Non-secret adjustable parameters belong in:

```text
config.yaml
```

Recommended shape:

```yaml
project:
  name: Atlas Workforce Text-to-SQL
  environment: development

database:
  type: duckdb
  path: data/atlas_workforce.duckdb
  read_only: true
  query_timeout_seconds: 10
  max_result_rows: 200

rag:
  embedding_model: BAAI/bge-small-en-v1.5
  reranker_model: cross-encoder/ms-marco-MiniLM-L6-v2
  retrieval_top_k: 20
  rerank_top_k: 4
  max_metadata_tokens: 450

vector_store:
  type: faiss
  index_type: IndexFlatIP
  index_path: data/faiss_index

sql:
  dialect: duckdb
  max_repair_attempts: 3
  allow_cross_join: false

api:
  request_timeout_seconds: 30
  max_attempts: 3
  initial_backoff_seconds: 1
  max_backoff_seconds: 8

structured_output:
  max_retries: 1

prompts:
  guardrail: guardrail_v1
  sql_generation: sql_generation_v1
  sql_repair: sql_repair_v1
  summary: summary_v1

logging:
  enabled: true
  log_path: logs/runs.jsonl
  level: INFO
```

---

## 19. Settings Loader

Centralize configuration in:

```text
src/config/settings.py
```

Use typed validation.

Do not scatter:

```python
yaml.safe_load(...)
os.getenv(...)
```

through unrelated modules.

Invalid settings should fail at startup.

---

## 20. Secrets

Real credentials must never be committed.

Local development:

```text
.env
```

Repository:

```text
.env.example
```

Example:

```text
LLM_PROVIDER=
LLM_MODEL=
LLM_API_KEY=
```

`.env` must be in `.gitignore`.

Public Streamlit deployment should use the platform's secret management rather than source-controlled credentials.

---

## 21. Preflight Checks

On application startup verify:

- DuckDB database exists
- FAISS index exists
- metadata files exist
- business context exists
- embedding model can load
- reranker can load
- required LLM credentials are configured

Errors should provide actionable instructions.

Example:

```text
FAISS index not found.
Run:
python scripts/build_vector_index.py
```

---

## 22. Logging / Observability

V1 can use:

```text
logs/runs.jsonl
```

One user question = one `run_id`.

Recommended logged fields:

- run ID
- timestamp
- question
- guardrail status
- retrieval candidates
- retrieval scores
- reranked tables
- reranker scores
- generated SQL
- model identifier
- prompt version
- SQL validation result
- actual AST tables used
- execution success/failure
- execution time
- result row count
- truncation flag
- SQL retry count
- retry history
- final status
- total latency

---

## 23. What Not to Log

Never log:

- API keys
- authorization headers
- secrets
- full environment files
- hidden model chain-of-thought

Do not persist full query results by default.

A small debug preview, e.g. first three rows, is acceptable.

---

## 24. Token and Cost Tracking

Where provider metadata is available, support:

```text
input_tokens
output_tokens
total_tokens
estimated_cost_usd
```

If unavailable, store null.

This enables later model comparison.

---

## 25. Latency Tracking

Measure at least:

```text
guardrail_latency
embedding_latency
faiss_latency
reranker_latency
sql_generation_latency
validation_latency
database_latency
summary_latency
total_latency
```

These should support evaluation and debugging.

---

## 26. Demo Observability vs Internal Logs

Streamlit may expose:

- Guardrail pass/reject
- retrieved table names
- generated SQL
- validation status
- execution status
- execution time
- retry count
- query result
- final answer

Do not expose:

- secrets
- full system prompts by default
- raw internal tracebacks
- hidden reasoning

---

## 27. Model Configuration Registry

Support named profiles:

```yaml
models:
  development:
    provider: TBD
    model: TBD

  benchmark:
    provider: TBD
    model: TBD

  deployment:
    provider: TBD
    model: TBD
```

This preserves flexibility while keeping the graph stable.

---

## 28. Model/API Layer Acceptance Criteria

This layer is complete when:

- provider SDKs are isolated behind adapters
- graph nodes do not depend directly on a specific vendor
- embedding/reranker run locally
- FAISS exact search works
- structured outputs are Pydantic-validated
- SQL validator blocks unsafe access
- DuckDB generated-query connection is read-only
- retry mechanisms are separated
- timeout/result limits are enforced
- secrets are not committed
- preflight checks are actionable
- run-level observability is recorded

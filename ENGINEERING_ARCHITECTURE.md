# Engineering Architecture

This document explains the Workforce Analytics Assistant as an agentic Text-to-SQL workflow. It follows one user question from the Streamlit UI through context handling, schema retrieval, SQL generation, validation, execution, repair, and final answer generation.

For product usage and demo steps, see `DETAILED_INSTRUCTIONS.md`.

## 1. Technology Stack By Module

| Module | Technologies | What They Do |
| --- | --- | --- |
| Product UI | Streamlit, custom CSS, `st.session_state` | Renders the chat interface, mode controls, sidebar info, current-session conversation state, and expandable workflow details. |
| Agent workflow orchestration | LangGraph `StateGraph`, typed `AgentState` | Executes the node-based agent flow and routes between guardrail, retrieval, SQL generation, validation, execution, repair, and summary. |
| LLM abstraction | Pydantic contracts, local `StubLLMService`, OpenAI-compatible chat-completions adapter | Provides deterministic Offline Demo behavior and Live API behavior through the same interface. |
| Structured output layer | Pydantic, JSON extraction, provider retry logic | Converts model responses into typed objects such as `GuardrailResult`, `SQLGenerationResult`, and `SummaryResult`. |
| Schema RAG pipeline | YAML metadata, table document serialization, hashing embeddings, numpy vector search, lexical reranking | Retrieves the most relevant table schema context before SQL generation. |
| Optional retrieval stack | `sentence-transformers`, FAISS, cross-encoder reranking | Supports heavier semantic retrieval experiments outside the lightweight deployed app path. |
| SQL safety layer | `sqlglot`, table allowlist, read-only query rules | Parses and validates generated SQL before it can reach the database. |
| Database execution | DuckDB, local `.duckdb` file, read-only connection, result row cap | Executes validated SQL against synthetic workforce analytics data. |
| Data foundation | pandas, numpy, generated CSVs, DuckDB build scripts, YAML metadata | Creates and ships the synthetic workforce dataset and schema documentation. |
| Testing and evaluation | pytest, synthetic fixtures, guardrail/retrieval/repair evaluation scripts, GitHub Actions | Keeps the workflow testable without API cost and verifies core demo paths on push. |
| Deployment | GitHub, Streamlit Community Cloud, Streamlit Secrets, `requirements.txt` | Hosts the app and injects Live API credentials securely at runtime. |

The key engineering idea is separation of concerns: the UI does not generate SQL, the LLM does not execute SQL, retrieval only selects schema context, validation gates all generated SQL, and DuckDB only sees validated read-only queries.

## 2. End-To-End Flow

The project is a Streamlit application backed by a LangGraph-style workflow, a synthetic DuckDB workforce database, a schema RAG pipeline, SQL validation, and an OpenAI-compatible LLM adapter.

One request moves through this path:

```text
User question
  -> Streamlit session state
  -> runtime service wiring
  -> optional follow-up resolution
  -> guardrail
  -> schema RAG retrieval
  -> SQL generation
  -> SQL validation
  -> DuckDB execution
  -> SQL repair, if needed
  -> natural-language summary
  -> chat answer + workflow details
```

Primary entrypoints:

```text
app.py
src/atlas_workforce/runtime.py
src/atlas_workforce/graph/workflow.py
```

The workflow is inspectable by design. Each run stores intermediate state such as retrieved tables, generated SQL, validation result, database result, repair attempts, and final answer.

## 3. UI And Session Layer

File:

```text
app.py
```

The Streamlit UI is intentionally thin. It does not build SQL directly. Its job is to collect the user question, choose runtime mode, preserve current-session conversation state, and render the workflow output.

Key responsibilities:

- Render the chat-style `Conversation` panel.
- Provide `Offline Demo` and `Live API` modes.
- Store visible chat turns in `st.session_state["chat_turns"]`.
- Store the previous agent result in `st.session_state["last_state"]`.
- Pass each question to `run_question`.
- Show the final answer first, then expandable workflow details.

Conversation memory is current-session only. The app can resolve short follow-ups while the page remains open, but it does not persist long-term chat history.

## 4. Runtime Service Wiring

File:

```text
src/atlas_workforce/runtime.py
```

The runtime layer builds the services that the graph needs for one run.

`build_workflow_services` wires together:

- LLM service: local stub or configured OpenAI-compatible provider.
- Business context loaded from `metadata/business_context.yaml`.
- Table schema documents built from `metadata/tables/*.yaml`.
- RAG embedder and vector store.
- Optional reranker.
- SQL validator.
- Read-only DuckDB executor.
- Graph retry limits and retrieval limits.

The mode selection happens here:

```text
Offline Demo -> StubLLMService
Live API     -> OpenAICompatibleLLMService
```

The deployed app uses lightweight retrieval by default:

```text
HashingEmbedder
NumpyVectorStore built in memory
LexicalReranker
```

This avoids downloading large embedding or reranking models on Streamlit Community Cloud.

## 5. Graph State

File:

```text
src/atlas_workforce/graph/state.py
```

Every node reads and writes a shared `AgentState`. Important fields include:

```text
run_id
user_question
resolved_question
is_follow_up
follow_up_reason
guardrail_allowed
guardrail_reason
retrieved_context
retrieved_tables
retrieval_scores
reranker_scores
generated_sql
llm_reported_tables
validation_result
validated_tables
db_result
db_error
sql_retry_count
retry_history
final_answer
status
```

This state is the contract between backend workflow and UI inspection. The Streamlit app uses it to render `Show workflow details`.

## 6. Follow-Up Resolution

Files:

```text
app.py
src/atlas_workforce/runtime.py
src/atlas_workforce/llm/service.py
src/atlas_workforce/llm/openai_compatible.py
```

Before the graph starts, `run_question` checks whether there is a previous state. If so, it asks the LLM service to resolve the new question into a standalone question.

Inputs:

```text
new question
previous question
previous SQL
previous answer
```

Outputs:

```text
resolved_question
is_follow_up
reason
```

Example:

```text
Previous question:
How many active employees are in each business unit?

New question:
What about Technology?

Resolved question:
How many active employees are in the Technology business unit?
```

The graph then uses `resolved_question` for guardrail, retrieval, SQL generation, repair, and summary.

## 7. Guardrail Node

File:

```text
src/atlas_workforce/graph/workflow.py
```

Node:

```text
guardrail
```

The guardrail classifies whether the question belongs to the supported workforce analytics scope.

Allowed scope:

```text
employees
organizations
talent_reviews
development_programs
employee_programs
internal_moves
```

If allowed, the graph continues to schema retrieval. If rejected, the run ends before SQL generation.

This protects the app from questions about:

- Real employee records.
- Salaries or protected attributes.
- Weather, market data, current events, or external facts.
- Legal, HR policy, or employment advice.

Provider errors during this step are surfaced as `API_ERROR` states instead of stack traces.

## 8. RAG Pipeline: Schema Context Construction

RAG is used to decide which schema context the SQL generator should see. The goal is not to answer from retrieved text directly; the goal is to give the SQL generation node the right tables, columns, keys, and metric context.

### 7.1 Source Metadata

Files:

```text
metadata/business_context.yaml
metadata/tables/*.yaml
```

Each table YAML contains:

- Table name.
- Description.
- Grain.
- Primary key.
- Foreign keys.
- Column names, types, and descriptions.
- Sample rows.

The six table metadata files are:

```text
organizations.yaml
employees.yaml
talent_reviews.yaml
development_programs.yaml
employee_programs.yaml
internal_moves.yaml
```

### 7.2 Table Document Serialization

File:

```text
src/atlas_workforce/rag/documents.py
```

`build_table_documents` loads each table YAML and converts it into a `TableDocument`:

```text
table_name
text
metadata
```

The serialized document includes:

```text
Table
Description
Grain
Primary key
Foreign keys
Columns
Sample rows
```

This creates one retrievable document per database table. Because the database has six tables, the deployed demo retrieves over a small but richly described schema corpus.

### 7.3 Embedding Backends

File:

```text
src/atlas_workforce/rag/embeddings.py
```

The app supports two embedding paths.

Deployed lightweight path:

```text
HashingEmbedder
```

`HashingEmbedder` tokenizes text, hashes tokens into a fixed 384-dimensional vector, applies signed token counts, and L2-normalizes the rows. It is deterministic, fast, and requires no model download.

Optional semantic path:

```text
SentenceTransformerEmbedder
```

This uses `sentence-transformers` with the configured embedding model, such as:

```text
BAAI/bge-small-en-v1.5
```

Optional dependencies are kept in `requirements-optional.txt` so the Streamlit deployment stays lightweight.

### 7.4 Vector Store Construction

Files:

```text
src/atlas_workforce/rag/retrieval.py
src/atlas_workforce/rag/vector_store.py
scripts/build_vector_index.py
```

Runtime in-memory path:

```text
metadata/tables/*.yaml
  -> TableDocument[]
  -> HashingEmbedder.encode_documents
  -> NumpyVectorStore
```

The in-memory `NumpyVectorStore` performs dot-product search over normalized vectors.

Optional persisted index path:

```text
scripts/build_vector_index.py
  -> build table documents
  -> encode documents
  -> save numpy or FAISS index
  -> data/faiss_index/
```

Supported vector store backends:

```text
numpy
faiss
```

The repository includes `data/faiss_index/` as an optional retrieval artifact, but the Streamlit app can rebuild a lightweight in-memory store at runtime.

### 7.5 Candidate Retrieval

File:

```text
src/atlas_workforce/rag/retrieval.py
```

At query time, retrieval does this:

```text
question
  -> embedder.encode_query(question)
  -> vector_store.search(query_embedding, retrieval_top_k)
  -> candidate table documents
```

Default limits come from `config.yaml`:

```text
retrieval_top_k: 20
rerank_top_k: 4
```

Because there are only six table documents, retrieval can consider the whole schema corpus, then return the top context after reranking.

### 7.6 Reranking

File:

```text
src/atlas_workforce/rag/reranker.py
```

The deployed app uses:

```text
LexicalReranker
```

It scores candidate tables using:

- Question/document token overlap.
- Table-specific aliases.
- Small boosts for important query patterns.
- A tiny contribution from the embedding retrieval score.

Example alias groups:

```text
employees -> employee, employees, workforce, headcount, active
organizations -> organization, org, business, unit, region
talent_reviews -> review, talent, performance, rating
internal_moves -> move, mobility, promotion, transfer
```

Optional production-style reranking uses:

```text
CrossEncoderReranker
```

If cross-encoder scores are invalid, it falls back to the lexical reranker.

### 7.7 Retrieved Context Sent To SQL Generation

The retrieval node writes these fields into `AgentState`:

```text
retrieved_context
retrieved_candidates
retrieved_tables
retrieval_scores
reranker_scores
status = SCHEMA_RETRIEVED
```

`retrieved_context` is the concatenated text of the selected table documents. This becomes the schema context for the SQL generation node.

In the UI, the user can inspect:

- Which tables were retrieved.
- Retrieval scores.
- Reranker scores.
- The generated SQL that used that context.

## 9. SQL Generation Node

Files:

```text
src/atlas_workforce/graph/workflow.py
src/atlas_workforce/llm/service.py
src/atlas_workforce/llm/openai_compatible.py
src/atlas_workforce/prompts/sql_generation_v1.txt
```

Node:

```text
generate_sql
```

Inputs:

```text
resolved question
business context
retrieved schema context
```

Output:

```text
SQLGenerationResult
  sql
  tables_used
```

In `Offline Demo`, `StubLLMService` uses deterministic rules for supported examples. In `Live API`, `OpenAICompatibleLLMService` calls a configured chat-completions API and asks for structured JSON.

The generator is instructed to produce one safe DuckDB `SELECT` query, but the result is not trusted until validation passes.

## 10. SQL Validation Node

File:

```text
src/atlas_workforce/sql/validator.py
```

Node:

```text
validate_sql
```

The validator uses `sqlglot` to parse and normalize SQL before execution.

It enforces:

- Exactly one SQL statement.
- Read-only `SELECT` or `WITH ... SELECT`.
- Allowed tables only.
- No external file, URL, extension, or table access.
- No cross joins by default.

The validator returns:

```text
is_valid
normalized_sql
tables_used
error_type
error_message
```

If validation passes, the graph continues to DuckDB execution. If validation fails, the graph routes to SQL repair unless the retry budget has been exhausted.

## 11. DuckDB Execution Node

File:

```text
src/atlas_workforce/sql/executor.py
```

Node:

```text
execute_sql
```

Database:

```text
data/atlas_workforce.duckdb
```

Execution behavior:

- Connects to DuckDB in read-only mode.
- Wraps the validated SQL in an outer row limit.
- Returns structured columns, rows, row count, truncation flag, and execution time.

Result shape:

```text
columns
rows
row_count
truncated
execution_time_ms
```

If execution fails because of a database error, the graph routes to SQL repair unless the retry budget has been exhausted.

## 12. SQL Repair Loop

Files:

```text
src/atlas_workforce/graph/workflow.py
src/atlas_workforce/llm/service.py
src/atlas_workforce/llm/openai_compatible.py
src/atlas_workforce/prompts/sql_repair_v1.txt
```

Node:

```text
repair_sql
```

Repair can be triggered by:

- SQL validation failure.
- DuckDB execution failure.

Inputs:

```text
question
business context
retrieved schema context
previous SQL
current error
retry history
```

The repaired SQL goes back through validation. It is not executed directly.

The retry budget is configured in `config.yaml`:

```text
max_repair_attempts: 3
```

The graph keeps:

```text
sql_retry_count
retry_history
```

This makes repair attempts visible in the UI.

## 13. Summary Node

Files:

```text
src/atlas_workforce/graph/workflow.py
src/atlas_workforce/llm/service.py
src/atlas_workforce/llm/openai_compatible.py
src/atlas_workforce/prompts/summary_v1.txt
```

Node:

```text
summarize
```

Inputs:

```text
question
generated SQL
database columns
database rows
truncated flag
```

Output:

```text
SummaryResult
  answer
```

The final answer is a natural-language summary grounded in the executed database result. The UI renders this answer directly in the chat, with the SQL and intermediate workflow details kept below it.

## 14. LLM Adapter Design

Files:

```text
src/atlas_workforce/llm/contracts.py
src/atlas_workforce/llm/service.py
src/atlas_workforce/llm/openai_compatible.py
src/atlas_workforce/llm/factory.py
```

The project uses an interface-based LLM layer so the graph does not care whether it is using the local stub or a real provider.

Structured contracts:

```text
GuardrailResult
FollowUpResolutionResult
SQLGenerationResult
SQLRepairResult
SummaryResult
```

`OpenAICompatibleLLMService` calls:

```text
{base_url}/chat/completions
```

with:

```text
temperature: 0
response_format: {"type": "json_object"}
```

It extracts JSON, validates the response with Pydantic, and retries once for malformed structured output.

Provider errors are converted into workflow states such as `API_ERROR`, which keeps failures inspectable rather than crashing the UI.

## 15. Data Layer

Synthetic data:

```text
data/generated/*.csv
data/atlas_workforce.duckdb
```

Generation/build scripts:

```text
scripts/generate_data.py
scripts/validate_data.py
scripts/build_database.py
```

Tables:

```text
employees
organizations
talent_reviews
development_programs
employee_programs
internal_moves
```

For table grain, relationships, controlled values, business metrics, and data boundaries, see `DATA_GUIDE.md`.

The synthetic data is committed to the repository so Streamlit Community Cloud can start the app without running data generation during deployment.

## 16. Deployment Architecture

Deployment path:

```text
GitHub repository
  -> Streamlit Community Cloud
  -> app.py
  -> local DuckDB file
  -> Streamlit Secrets for LLM credentials
```

Important deployment files:

```text
app.py
requirements.txt
config.yaml
.streamlit/config.toml
data/atlas_workforce.duckdb
data/generated/*.csv
metadata/
src/
```

Live API secrets are configured in Streamlit Community Cloud using TOML:

```toml
LLM_PROVIDER = "openai_compatible"
LLM_MODEL = "<model-id>"
LLM_API_KEY = "<your-api-key>"
LLM_BASE_URL = "<provider-base-url>"
```

Root-level Streamlit secrets are exposed as environment variables at runtime, which the app reads through the settings/env loader.

## 17. Testing Strategy

Tests live under:

```text
tests/
```

Coverage includes:

- Synthetic data integrity.
- Schema document construction and retrieval.
- Guardrail behavior.
- LLM adapter structured output handling.
- Runtime happy path.
- Homepage Offline Demo example coverage.
- SQL validation.
- SQL repair paths.
- Stub summary behavior.
- Evaluation utilities.

Current status:

```text
50 passed, 1 warning
```

GitHub Actions runs the test suite and preflight checks on pushes and pull requests to `main`.

## 18. Design Tradeoffs

### Streamlit Instead Of A Full Frontend Stack

Streamlit was chosen for fast iteration and simple deployment. The goal was to build a working analytics assistant, not a custom frontend framework.

### DuckDB Instead Of Postgres

DuckDB was chosen because the dataset is synthetic, local, and easy to ship with a portfolio demo.

### Stub Mode Plus Live API Mode

The stub keeps demos and tests deterministic. Live API mode shows realistic model behavior.

Tradeoff:

- Offline Demo is narrower.
- Live API depends on provider quality, latency, and cost.

### Lightweight RAG In The Deployed App

The deployed app uses hashing and lexical retrieval rather than heavy embedding models.

Tradeoff:

- Faster and easier cloud deployment.
- Less semantically powerful than production embedding retrieval.

### Current-Session Memory Only

The app supports lightweight follow-up questions using the previous run state.

Tradeoff:

- Simple and transparent.
- No long-term chat history or user-specific memory.

## 19. Safety Boundaries

Safety mechanisms:

- Synthetic data only.
- Guardrail classification before SQL generation.
- Schema-scoped SQL generation.
- SQL parser validation before execution.
- Read-only DuckDB execution.
- Allowed table list.
- No external access functions.
- Bounded repair attempts.
- Result row cap.

Out of scope:

- Real employee records.
- Salary data.
- Protected attributes.
- External facts such as weather, markets, or current events.
- Production HR decision-making.

## 20. Future Improvements

Potential next steps:

- Add persistent conversation history.
- Add a semantic metric layer.
- Add richer SQL evaluation with Live API mode.
- Add more synthetic tables and benchmark questions.
- Add authentication for private demos.
- Add query cost and latency telemetry.
- Add chart generation for tabular results.
- Add stronger prompt/version tracking.

## 21. Quick Reviewer Path

If you only have a few minutes:

1. Open the Streamlit app.
2. Ask: `How many active employees are in each business unit?`
3. Ask: `What about Technology?`
4. Open `Show workflow details`.
5. Review `src/atlas_workforce/graph/workflow.py`.
6. Review `src/atlas_workforce/rag/retrieval.py`.
7. Review `src/atlas_workforce/sql/validator.py`.
8. Review `src/atlas_workforce/llm/openai_compatible.py`.

That path shows the product, the agent workflow, the RAG pipeline, the validation layer, and the provider adapter.

# Engineering Architecture

This document is a concise engineering overview for technical reviewers. It explains how the Workforce Analytics Assistant is structured, how a request moves through the system, and why the main design choices were made.

For product usage and exploration steps, see `DETAILED_INSTRUCTIONS.md`.

## 1. System Overview

The project is a Streamlit Text-to-SQL application backed by a LangGraph-style agent workflow, a synthetic DuckDB workforce database, SQL validation, schema retrieval, and an OpenAI-compatible LLM adapter.

High-level architecture:

```text
Streamlit UI
  -> runtime service wiring
  -> LangGraph workflow
  -> LLM service / stub service
  -> schema retrieval
  -> SQL validation
  -> DuckDB execution
  -> natural-language summary
```

Primary entrypoints:

```text
app.py
src/atlas_workforce/runtime.py
src/atlas_workforce/graph/workflow.py
```

## 2. Request Flow

When a user submits a question, the app runs this flow:

```text
User question
  -> Optional follow-up resolution
  -> Guardrail
  -> Schema retrieval
  -> SQL generation
  -> SQL validation
  -> DuckDB execution
  -> SQL repair, if validation or execution fails
  -> Natural-language summary
  -> Streamlit chat response
```

The UI stores the visible chat and previous agent state in `st.session_state`. For follow-up questions, the runtime passes the previous question, SQL, and answer to the LLM service so the new question can be resolved into a standalone workforce analytics question.

## 3. Core Components

### `app.py`

Responsibilities:

- Render the Streamlit UI.
- Provide `Offline Demo` and `Live API` mode selection.
- Maintain current-session chat state.
- Submit questions into the runtime.
- Display answer bubbles.
- Display expandable workflow details.
- Document product scope in the sidebar.

The frontend is intentionally thin. It does not generate SQL directly; it delegates the agent run to `run_question`.

### `src/atlas_workforce/runtime.py`

Responsibilities:

- Load settings.
- Build table metadata documents.
- Select LLM implementation.
- Configure retrieval backend.
- Create SQL validator and DuckDB executor.
- Build workflow services.
- Run the compiled graph.

Important function:

```python
run_question(settings, root, question, options, previous_state=None, force_follow_up=False)
```

### `src/atlas_workforce/graph/workflow.py`

Defines the graph execution.

Main nodes:

```text
guardrail
retrieve_schema
generate_sql
validate_sql
execute_sql
repair_sql
summarize
```

Conditional transitions:

- Guardrail rejection ends the run.
- SQL validation failure goes to repair unless retry limit is reached.
- Database execution failure goes to repair unless retry limit is reached.
- Successful execution goes to summary.

### `src/atlas_workforce/graph/state.py`

Defines the shared `AgentState`.

Important state fields:

```text
run_id
user_question
resolved_question
is_follow_up
guardrail_allowed
guardrail_reason
retrieved_context
retrieved_tables
generated_sql
validation_result
db_result
db_error
sql_retry_count
retry_history
final_answer
status
```

This state object is what makes the workflow inspectable in the UI.

## 4. LLM Layer

The project uses an interface-based LLM design.

### Offline Stub

File:

```text
src/atlas_workforce/llm/service.py
```

`StubLLMService` provides deterministic local behavior for:

- Guardrail checks.
- Supported SQL generation examples.
- SQL repair demos.
- Summary generation.
- Lightweight follow-up resolution.

This makes the project testable and demoable without API cost.

### Live API Adapter

File:

```text
src/atlas_workforce/llm/openai_compatible.py
```

`OpenAICompatibleLLMService` calls OpenAI-compatible chat completion APIs and expects structured JSON responses for:

- `GuardrailResult`
- `FollowUpResolutionResult`
- `SQLGenerationResult`
- `SQLRepairResult`
- `SummaryResult`

The adapter includes JSON extraction and Pydantic validation so the workflow can work with typed outputs instead of raw text.

## 5. Retrieval Layer

Files:

```text
src/atlas_workforce/rag/documents.py
src/atlas_workforce/rag/embeddings.py
src/atlas_workforce/rag/retrieval.py
src/atlas_workforce/rag/reranker.py
src/atlas_workforce/rag/vector_store.py
```

The app builds schema documents from table metadata under:

```text
metadata/
```

In the Streamlit demo, retrieval uses:

```text
HashingEmbedder
LexicalReranker
```

This keeps deployment lightweight and avoids downloading large models on Streamlit Community Cloud.

Optional production-style retrieval experiments are supported through:

```text
requirements-optional.txt
```

Optional components include:

- `sentence-transformers`
- `faiss-cpu`
- cross-encoder reranking

## 6. SQL Safety And Validation

File:

```text
src/atlas_workforce/sql/validator.py
```

The SQL validator uses `sqlglot` to parse and normalize SQL before execution.

It enforces:

- Exactly one SQL statement.
- Read-only `SELECT` or `WITH ... SELECT` queries.
- No external file, URL, extension, or table access.
- No unauthorized table usage.
- No cross joins by default.

The validator returns a structured result:

```text
is_valid
normalized_sql
tables_used
error_type
error_message
```

Invalid SQL can trigger the repair node, up to a bounded retry limit.

## 7. Database Execution

File:

```text
src/atlas_workforce/sql/executor.py
```

Database:

```text
data/atlas_workforce.duckdb
```

Execution properties:

- DuckDB local file.
- Read-only execution mode.
- Result row cap.
- Structured database result returned to the graph.

DuckDB was chosen because it is simple to ship with a portfolio/demo project and does not require external database infrastructure.

## 8. Data And Metadata

Synthetic data:

```text
data/generated/*.csv
data/atlas_workforce.duckdb
```

Metadata:

```text
metadata/business_context.yaml
metadata/tables/*.yaml
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

The synthetic data is intentionally committed to the repository so Streamlit Community Cloud can start the app without running generation scripts at deployment time.

## 9. Deployment Architecture

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

## 10. Testing Strategy

Tests live under:

```text
tests/
```

Coverage includes:

- Synthetic data integrity.
- Schema retrieval behavior.
- Guardrail behavior.
- LLM adapter structured output handling.
- Runtime happy path.
- SQL validation.
- SQL repair paths.
- Stub summary behavior.
- Evaluation utilities.

Current status:

```text
50 passed, 1 warning
```

The stub path is important because it makes most logic testable without relying on external API availability.

## 11. Design Tradeoffs

### Streamlit Instead Of A Full Frontend Stack

Streamlit was chosen for fast iteration and simple deployment. The goal was to build a working analytics assistant, not a custom frontend framework.

Tradeoff:

- Faster product iteration.
- Less control than React or a custom web stack.

### DuckDB Instead Of Postgres

DuckDB was chosen because the dataset is synthetic and local.

Tradeoff:

- Easy to ship and deploy.
- Not representative of multi-user production database infrastructure.

### Stub Mode Plus Live API Mode

The stub keeps demos and tests deterministic. Live API mode shows realistic model behavior.

Tradeoff:

- Offline Demo is narrow.
- Live API depends on provider quality and cost.

### Lightweight Retrieval In The Deployed App

The deployed app uses hashing and lexical retrieval rather than heavy embedding models.

Tradeoff:

- Faster and easier cloud deployment.
- Less semantically powerful than production embedding retrieval.

### Current-Session Memory Only

The app supports lightweight follow-up questions using the previous run state.

Tradeoff:

- Simple and transparent.
- No long-term chat history or user-specific memory.

## 12. Safety And Boundaries

Safety mechanisms:

- Synthetic data only.
- Guardrail classification before SQL generation.
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

## 13. Future Improvements

Potential next steps:

- Add persistent conversation history.
- Add a semantic metric layer.
- Add richer SQL evaluation with Live API mode.
- Add more synthetic tables and benchmark questions.
- Add authentication for private demos.
- Add query cost and latency telemetry.
- Add chart generation for tabular results.
- Add stronger prompt/version tracking.
- Add CI on GitHub Actions.

## 14. Quick Reviewer Path

If you only have a few minutes:

1. Open the Streamlit app.
2. Ask: `How many active employees are in each business unit?`
3. Ask: `What about Technology?`
4. Open `Show workflow details`.
5. Review `src/atlas_workforce/graph/workflow.py`.
6. Review `src/atlas_workforce/sql/validator.py`.
7. Review `src/atlas_workforce/llm/openai_compatible.py`.

That path shows the product, the agent workflow, the validation layer, and the provider adapter.

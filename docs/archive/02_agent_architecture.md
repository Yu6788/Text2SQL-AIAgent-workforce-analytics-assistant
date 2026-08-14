# Atlas Workforce Text-to-SQL — Agent Architecture

## 1. Objective

Implement the Text-to-SQL workflow with LangGraph using explicit, testable nodes.

Business-level concept:

```text
Guardrail
-> SQL Generation
-> Database
-> Summary
or
-> Retry
```

Code-level graph should be decomposed more precisely so each stage can be independently tested and evaluated.

---

## 2. Node Graph

```text
User Question
      |
      v
+------------------+
| Guardrail        |
+------------------+
      |
      +---- rejected --------------------------> END
      |
      v
+------------------+
| Retrieval        |
+------------------+
      |
      v
+------------------+
| Reranker         |
+------------------+
      |
      v
+------------------+
| Prompt Builder   |
+------------------+
      |
      v
+------------------+
| SQL Generation   |
+------------------+
      |
      v
+------------------+
| SQL Validator    |
+------------------+
      |
      +---- fail -------------------+
      |                             |
      v                             |
+------------------+                |
| DuckDB Executor  |                |
+------------------+                |
      |                             |
      +---- success -> Summary      |
      |                             |
      +---- fail -------------------+
                                    |
                                    v
                              +-------------+
                              | SQL Repair  |
                              +-------------+
                                    |
                                    v
                              SQL Validator
                                    |
                                    v
                              DuckDB Executor
                                    |
                         max SQL repair attempts
                                    |
                                    v
                               Fail / END
```

---

## 3. Shared Graph State

The graph state should include at minimum:

```python
run_id
user_question

guardrail_allowed
guardrail_reason

retrieved_candidates
retrieved_tables
retrieved_context
retrieval_scores
reranker_scores

business_context

sql_generation_prompt
generated_sql
llm_reported_tables

validation_result
validated_tables

db_result
db_columns
db_error
result_truncated

sql_retry_count
retry_history

final_answer
status

latency
model_usage
prompt_versions
```

Use typed structures such as TypedDict and/or Pydantic models.

---

## 4. Guardrail Node

### Purpose

Determine whether the user question can reasonably be answered from the available workforce analytics database.

It is **not** a SQL syntax classifier.

### Allowed Examples

- Which organization has the highest active headcount?
- What was the promotion rate in 2026?
- Which programs had the lowest completion rate?

### Rejected Examples

- What is the weather today?
- Write me a poem.
- What is Bitcoin's current price?

### Output Contract

```python
class GuardrailResult(BaseModel):
    allowed: bool
    reason: str
```

Rejected questions terminate the graph.

---

## 5. Retrieval Node

### Input

- user question
- table metadata documents

### Process

1. Prefix the question appropriately for the embedding model.
2. Create a normalized query embedding.
3. Query FAISS.
4. Retrieve:

```text
min(retrieval_top_k, number_of_indexed_tables)
```

V1 config:

```text
retrieval_top_k = 20
```

With six tables, runtime candidates will be all six ranked by similarity.

### Output

- candidate table documents
- similarity scores

---

## 6. Reranker Node

### Input

- user question
- FAISS candidates

### Process

Use a local CrossEncoder to score `(question, table_metadata)` pairs.

Keep:

```text
rerank_top_k = 4
```

### Output

- Top-4 table metadata
- reranker scores

Preserve reranker order when constructing the SQL prompt.

Do not pass numeric reranker scores to the LLM prompt.

---

## 7. Prompt Builder Node

### Input

- user question
- global business definitions
- Top-4 table metadata
- prompt version configuration

### Output

The assembled SQL-generation prompt.

Prompt structure:

```text
SQL SYSTEM INSTRUCTIONS
+
BUSINESS DEFINITIONS
+
RERANKED TABLE METADATA
+
USER QUESTION
```

---

## 8. SQL Generation Node

### Purpose

Generate a single read-only DuckDB analytical query.

### Rules

- use only supplied tables and columns
- do not invent schema
- use documented relationships
- follow business definitions
- DuckDB-compatible SQL
- one query only
- no database mutation
- no external data access

### Output Contract

```python
class SQLGenerationResult(BaseModel):
    sql: str
    tables_used: list[str]
```

`tables_used` is model metadata only.

The authoritative actual table list comes later from SQLGlot AST parsing.

Do not request or store chain-of-thought.

---

## 9. SQL Validator Node

### Purpose

Deterministically verify safety and structural policy before DuckDB execution.

### Implementation

Use SQLGlot with DuckDB dialect.

### Required Checks

1. SQL parses successfully.
2. Exactly one statement.
3. Query is read-only.
4. `SELECT` and `WITH ... SELECT` are allowed.
5. Mutation/DDL statements are rejected.
6. Only whitelisted V1 tables are used.
7. CTE names are permitted as internal query sources.
8. External table/file functions are rejected.
9. `CROSS JOIN` is rejected in V1.

### V1 Table Whitelist

```text
organizations
employees
talent_reviews
development_programs
employee_programs
internal_moves
```

### Examples of Disallowed Operations

```text
INSERT
UPDATE
DELETE
DROP
ALTER
CREATE
TRUNCATE
MERGE
COPY
ATTACH
DETACH
INSTALL
LOAD
PRAGMA
```

### Output Contract

```python
class SQLValidationResult(BaseModel):
    is_valid: bool
    normalized_sql: str | None
    tables_used: list[str]
    error_type: str | None
    error_message: str | None
```

Validation failure routes to SQL Repair if the SQL retry budget remains.

---

## 10. Database Executor Node

### Database

DuckDB.

Open generated-query connections as read-only.

### Protections

```text
query_timeout_seconds = 10
max_result_rows = 200
```

### Result Limit Strategy

Execute a safe wrapper that can detect whether more than 200 rows exist.

Conceptually:

```sql
SELECT *
FROM (
    <validated generated query>
) AS result
LIMIT 201
```

If 201 rows are returned:

- expose only first 200
- set `result_truncated = true`

### Output Contract

```python
class QueryResult(BaseModel):
    columns: list[str]
    rows: list
    row_count: int
    truncated: bool
    execution_time_ms: float
```

Zero rows are an execution success and should not automatically trigger SQL repair.

---

## 11. SQL Repair Node

### Trigger

Either:

- SQL Validator failure
- DuckDB execution failure
- query timeout that is plausibly fixable by a simpler query

### Input

- original user question
- business definitions
- original retrieved schema context
- previous SQL
- current error
- compact retry history

Do not rerun retrieval.

### Output Contract

```python
class SQLRepairResult(BaseModel):
    sql: str
```

The repaired SQL returns to the Validator.

---

## 12. SQL Retry Budget

Use one shared SQL repair counter for validation and execution failures.

```text
max_sql_repair_attempts = 3
```

Do not create:

- three validator retries
- plus three database retries

The shared SQL-repair budget prevents a six-attempt loop.

API retries are separate.

Structured-output retries are separate.

---

## 13. Summary Node

### Trigger

Only after successful DuckDB execution.

### Input

- original question
- final SQL
- result columns
- result rows
- truncation flag

### Rules

- answer only from database results
- do not invent facts
- convert ratios to understandable percentages where appropriate
- clearly handle zero rows
- mention truncation when relevant
- keep response concise

### Output Contract

```python
class SummaryResult(BaseModel):
    answer: str
```

---

## 14. Failure Classification

Suggested status/error values:

```text
SUCCESS
REJECTED_BY_GUARDRAIL

API_ERROR
MODEL_OUTPUT_ERROR

SQL_PARSE_ERROR
UNSAFE_SQL
UNAUTHORIZED_TABLE
EXTERNAL_ACCESS_ATTEMPT
CROSS_JOIN_NOT_ALLOWED

DATABASE_BINDER_ERROR
DATABASE_EXECUTION_ERROR
QUERY_TIMEOUT

MAX_SQL_RETRIES_EXCEEDED
SYSTEM_ERROR
```

---

## 15. Repairable vs Non-Repairable Failures

### SQL Repair May Handle

- syntax error
- hallucinated column
- hallucinated table caught by validator
- invalid join
- unsupported cross join
- DuckDB binder error
- query timeout caused by poor SQL shape

### SQL Repair Should Not Handle

- missing database file
- missing FAISS index
- missing API key
- invalid API credentials
- provider unavailable after infrastructure retry budget
- embedding model cannot load

These are system/infrastructure errors.

---

## 16. Runtime Semantic Validation

V1 does **not** add a separate LLM critic to decide whether successfully executed SQL semantically answers the question.

Distinguish:

```text
SQL Validator
= Is the query safe and structurally allowed?

DuckDB
= Can it execute?

Evaluation
= Does it return the same result as gold SQL?
```

Semantic correctness is measured offline through evaluation.

---

## 17. Human Intervention

V1 does not require true LangGraph interrupt/resume.

After the SQL repair budget is exhausted:

```text
status = MAX_SQL_RETRIES_EXCEEDED
```

Return a concise failure message.

A future version may add real human-in-the-loop resume behavior.

---

## 18. Architecture Acceptance Criteria

The graph is complete when:

- every node has a clear typed input/output contract
- unrelated questions terminate at Guardrail
- retrieval and reranking are separate
- SQL prompt construction is inspectable
- generated SQL is validated before execution
- only approved read-only queries reach DuckDB
- validation/execution failure routes to SQL Repair
- SQL repair never reruns RAG
- SQL retry budget is bounded
- API retry does not modify SQL retry counters
- successful execution reaches Summary
- all major intermediate artifacts are loggable

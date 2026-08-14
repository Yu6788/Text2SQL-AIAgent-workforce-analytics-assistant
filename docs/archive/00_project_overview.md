# Atlas Workforce Text-to-SQL — Project Overview

## 1. Purpose

Build a **fully runnable, end-to-end Text-to-SQL portfolio system** for workforce and talent-management analytics.

The system is not a pseudocode exercise. A reviewer should be able to:

1. Clone the repository.
2. Install dependencies.
3. Generate the synthetic workforce dataset.
4. Build the local DuckDB database.
5. Build the FAISS schema index.
6. Configure an LLM provider.
7. Run the application.
8. Ask a natural-language workforce analytics question.
9. Inspect retrieved tables and generated SQL.
10. See the SQL execute against DuckDB.
11. Observe automatic SQL repair when execution or validation fails.
12. Receive a concise natural-language answer.

The project is intended for:

- GitHub portfolio presentation
- local development
- technical interview walkthroughs
- reproducible evaluation
- later Streamlit deployment

All business data must be synthetic. Do not include real employee data, Amazon internal data, or any other proprietary records.

---

## 2. Business Scenario

The fictional company is **Atlas Workforce Solutions**.

Atlas supports workforce and talent-management analytics for a large enterprise. The target users include:

- Product Managers
- Program Managers
- Business Intelligence Engineers
- Data Scientists
- HR Business Partners
- Talent Management leaders

Users want to answer questions about:

- active workforce
- headcount by organization or business unit
- talent and performance reviews
- promotion recommendations
- internal mobility
- development-program enrollment and completion
- historical workforce trends

Example questions:

- How many active employees are in each business unit?
- Which organization has the highest active headcount?
- What was the 2026 H1 review completion rate?
- Which business unit had the highest average performance rating in 2026 H1?
- Which development program had the highest completion rate?
- How many employees were promoted in Q2 2026?
- Which organizations lost the most employees through internal transfers?
- Did employees who completed leadership-development programs have a higher later promotion rate?

---

## 3. V1 Scope

V1 contains exactly six analytical tables:

1. `organizations`
2. `employees`
3. `talent_reviews`
4. `development_programs`
5. `employee_programs`
6. `internal_moves`

V1 intentionally does **not** include employee-facing product clickstream/event data. That is a possible V2 extension.

---

## 4. Core Technology Stack

Use:

- Python
- LangGraph
- RAG
- FAISS
- local embedding model
- local CrossEncoder reranker
- configurable external LLM provider
- DuckDB
- SQLGlot
- YAML
- Pydantic / TypedDict where appropriate
- pytest
- Streamlit later for the demo UI

The system should favor:

> reproducibility, observability, modularity, and a complete working path

over unnecessary architectural complexity.

---

## 5. High-Level Workflow

```text
User Question
      |
      v
Guardrail
      |
      +---- rejected --------------------------> Final rejection
      |
      v
Embedding
      |
      v
FAISS Retrieval
      |
      v
CrossEncoder Reranking
      |
      v
Prompt Builder
      |
      v
SQL Generation
      |
      v
SQL Validator
      |
      +---- validation failure ----+
      |                            |
      v                            |
DuckDB Execution                   |
      |                            |
      +---- success ----> Summary  |
      |                            |
      +---- execution failure -----+
                                   |
                                   v
                               SQL Repair
                                   |
                                   v
                              SQL Validator
                                   |
                                   v
                             DuckDB Execution
                                   |
                         max 3 SQL repair attempts
                                   |
                                   v
                               Fail / Escalate
```

---

## 6. Key V1 Design Decisions

### Database

- DuckDB
- local database file
- read-only execution for generated SQL
- query timeout: 10 seconds
- maximum displayed result rows: 200

### RAG

- one table = one metadata document / chunk
- embedding model: `BAAI/bge-small-en-v1.5`
- normalized embeddings
- FAISS `IndexFlatIP`
- retrieval top-k config: 20
- runtime retrieval candidate count: `min(20, number_of_tables)`
- reranker: `cross-encoder/ms-marco-MiniLM-L6-v2`
- rerank top-k: 4
- V1 language: English
- target metadata document size: approximately 450 tokens or less

### LLM Layer

- provider-agnostic abstraction
- exact provider/model remains configurable and is **not locked before Phase 3**
- structured output required for all LLM-facing nodes
- no hidden chain-of-thought stored or exposed

### SQL Safety

- SQLGlot parser
- DuckDB dialect
- exactly one statement
- read-only query only
- `SELECT` and `WITH ... SELECT` allowed
- only whitelisted V1 tables
- no external table/file access
- no `CROSS JOIN` in V1
- DuckDB opened in read-only mode

### Retry Separation

There are three separate retry mechanisms:

1. API/infrastructure retry
2. structured-output retry
3. SQL repair retry

They must not share counters.

---

## 7. Repository Layout

Recommended structure:

```text
workforce-text-to-sql/
|
|-- README.md
|-- requirements.txt
|-- .env.example
|-- .gitignore
|-- config.yaml
|-- app.py
|
|-- docs/
|   |-- 00_project_overview.md
|   |-- 01_data_and_schema.md
|   |-- 02_agent_architecture.md
|   |-- 03_model_and_api.md
|   `-- 04_evaluation_and_demo.md
|
|-- src/
|   |-- config/
|   |   `-- settings.py
|   |
|   |-- graph/
|   |   |-- state.py
|   |   |-- workflow.py
|   |   `-- nodes/
|   |       |-- guardrail.py
|   |       |-- retrieval.py
|   |       |-- reranker.py
|   |       |-- prompt_builder.py
|   |       |-- sql_generator.py
|   |       |-- sql_validator.py
|   |       |-- executor.py
|   |       |-- sql_repair.py
|   |       `-- summarizer.py
|   |
|   |-- rag/
|   |   |-- embeddings.py
|   |   |-- vector_store.py
|   |   |-- reranker.py
|   |   `-- metadata_loader.py
|   |
|   |-- database/
|   |   |-- base.py
|   |   `-- duckdb_client.py
|   |
|   |-- models/
|   |   |-- base.py
|   |   |-- factory.py
|   |   `-- providers/
|   |
|   `-- prompts/
|       |-- guardrail_v1.txt
|       |-- sql_generation_v1.txt
|       |-- sql_repair_v1.txt
|       `-- summary_v1.txt
|
|-- metadata/
|   |-- business_context.yaml
|   `-- tables/
|
|-- data/
|   |-- generated/
|   `-- atlas_workforce.duckdb
|
|-- scripts/
|   |-- generate_data.py
|   |-- validate_data.py
|   |-- build_database.py
|   `-- build_vector_index.py
|
|-- evaluation/
|   |-- questions.json
|   |-- guardrail_questions.json
|   |-- evaluate_retrieval.py
|   |-- evaluate_sql.py
|   `-- results/
|
|-- logs/
|   `-- runs.jsonl
|
|-- assets/
|   `-- demo.gif
|
`-- tests/
```

---

## 8. Implementation Order

### Phase 1 — Data Foundation

1. Create repository skeleton.
2. Create configuration loader.
3. Implement deterministic synthetic data generation.
4. Validate all data relationships.
5. Build DuckDB.
6. Create table metadata YAML.
7. Create business metric definitions.
8. Verify representative SQL manually.

### Phase 2 — Retrieval

9. Load metadata.
10. Convert each table YAML into one clean retrieval document.
11. Generate local embeddings.
12. Build FAISS index.
13. Implement retrieval.
14. Implement reranking.
15. Evaluate table retrieval.

### Phase 3 — Agent Graph

16. Select/configure an LLM provider.
17. Implement provider abstraction.
18. Implement graph state.
19. Implement Guardrail.
20. Implement Prompt Builder.
21. Implement SQL Generation.
22. Implement SQL Validator.
23. Implement DuckDB Executor.
24. Implement SQL Repair.
25. Implement Summary.
26. Wire LangGraph conditional routing.

### Phase 4 — Evaluation

27. Build the evaluation dataset.
28. Add gold SQL.
29. Measure retrieval.
30. Measure execution accuracy.
31. Measure retry recovery.
32. Record latency and provider usage where available.

### Phase 5 — Portfolio Layer

33. Build Streamlit UI.
34. Add README screenshots/GIF.
35. Add reproducible setup instructions.
36. Optionally deploy a public demo.

---

## 9. V1 Non-Goals

Do not add:

- production authentication
- cloud data warehouse deployment
- PostgreSQL or Redshift as required backends
- Kubernetes
- arbitrary multi-agent collaboration
- column-level RAG
- parent-child retrieval
- production HR eligibility rules
- semantic SQL critic at runtime
- real employee PII
- product clickstream data
- true human interrupt/resume
- distributed data processing
- multilingual retrieval

These may be future extensions.

---

## 10. Acceptance Criteria

V1 is complete only when:

- synthetic data is generated from code
- the data passes integrity checks
- DuckDB builds locally
- all six tables are queryable
- all six metadata YAML files exist
- business definitions exist
- FAISS index builds successfully
- local embedding retrieval works
- reranking returns Top-4 metadata
- Guardrail rejects unrelated questions
- valid questions reach SQL generation
- generated SQL is validated before execution
- DuckDB executes only read-only approved SQL
- validation or execution failures can trigger SQL repair
- SQL repair stops after the configured maximum
- successful results reach Summary
- the user can inspect retrieved tables and generated SQL
- evaluation scripts run end-to-end
- README instructions reproduce the project from scratch
- no real proprietary workforce data is included

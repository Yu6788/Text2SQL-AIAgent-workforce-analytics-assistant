# Atlas Workforce Text-to-SQL — Evaluation and Demo Specification

## 1. Objective

This document defines how to prove that the system works.

The evaluation should answer:

- Does Guardrail classify questions correctly?
- Does RAG retrieve the required tables?
- Does the reranker improve retrieval?
- Does generated SQL return the correct result?
- Does SQL repair recover failed queries?
- How fast is the system?
- What model/API cost is associated with each query?
- Can a reviewer understand the system quickly from GitHub and Streamlit?

---

## 2. SQL Evaluation Dataset

Create:

```text
evaluation/questions.json
```

V1 target:

```text
80 questions
```

Difficulty distribution:

```text
20 Easy
35 Medium
25 Hard
```

---

## 3. Difficulty Design

### Easy

Focus on:

- one table
- filters
- COUNT
- AVG
- basic GROUP BY
- sorting
- simple date filtering

Examples:

- How many active employees are there?
- What is the average performance rating in 2026 H1?

### Medium

Focus on:

- two- or three-table joins
- business-unit aggregation
- ratios
- conditional aggregation
- quarter/year filters
- promotion analysis

Examples:

- Which business unit had the highest average performance rating in 2026 H1?
- Which organization had the highest promotion recommendation rate?

### Hard

Focus on:

- three- or four-table joins
- CTEs
- historical comparisons
- temporal relationships
- program completion followed by later promotion
- mobility trends

Example:

- Did employees who completed Leadership Development programs have a higher later promotion rate than employees who did not?

---

## 4. Evaluation Case Schema

Each case should contain:

```json
{
  "id": "Q042",
  "question": "Which business unit had the highest average performance rating in 2026 H1?",
  "difficulty": "medium",
  "category": "multi_table_aggregation",
  "expected_tables": [
    "talent_reviews",
    "employees",
    "organizations"
  ],
  "gold_sql": "SELECT ...",
  "notes": "Requires joining review records to employee organization membership."
}
```

Gold natural-language answers are optional and not required for V1.

---

## 5. Primary Metric: Execution Accuracy

Do not use exact SQL string match as the primary metric.

Instead:

```text
Gold SQL
   -> DuckDB
   -> Gold Result

Generated SQL
   -> DuckDB
   -> Generated Result
```

A generated query is correct when its result is equivalent to the gold result under the evaluation's comparison rules.

Primary metric:

```text
Execution Accuracy
=
queries with correct execution result
/
total evaluated questions
```

---

## 6. Result Comparison

The evaluator should normalize results where necessary.

Consider:

- column order when semantically irrelevant
- row ordering when the query does not define order
- floating point tolerance
- percentage/decimal representation
- null equivalence where appropriate

Do not treat different SQL syntax as wrong if the result is correct.

---

## 7. Retrieval Metrics

For each question, use `expected_tables`.

Report:

### Average Table Recall@4

For each question:

```text
required tables found in Top 4
/
required tables
```

Then average across questions.

### All-Required-Tables Recall@4

Percentage of questions where every required table appears in the Top 4.

This is especially useful for diagnosing whether SQL failure originates in RAG or generation.

---

## 8. Retrieval Ablation

Compare:

```text
FAISS only
vs
FAISS + CrossEncoder reranker
```

Report retrieval metrics for both.

Do not assume reranking improves performance.

If the six-table V1 schema shows little incremental gain, document that result honestly and note that reranking is retained for future larger-schema expansion.

---

## 9. SQL Repair Evaluation

Track:

### Initial Execution Accuracy

Correct before SQL repair.

### Retry Recovery Rate

```text
initially failed queries successfully recovered
/
initially failed queries
```

### Final Execution Accuracy

Correct after the SQL repair loop finishes.

These metrics demonstrate whether the repair mechanism actually adds value.

---

## 10. Guardrail Evaluation

Create:

```text
evaluation/guardrail_questions.json
```

Target:

```text
20 questions
```

Suggested:

```text
10 database-answerable
10 unrelated
```

Examples of unrelated:

- What is the weather today?
- Write a sorting algorithm.
- What is Bitcoin's current price?

Examples of answerable:

- Which organization has the highest headcount?
- What was the 2025 promotion rate?

At minimum report:

```text
Guardrail Accuracy
```

Precision/Recall may be stored in the detailed evaluation report.

---

## 11. Latency Evaluation

Record stage-level and end-to-end latency.

Primary portfolio metric:

```text
Median End-to-End Latency
```

Detailed report may also include:

```text
P95 latency
```

Do not invent latency values before measuring them.

---

## 12. Token and Cost Evaluation

If the selected provider exposes token usage, record:

- average input tokens
- average output tokens
- average total tokens
- average estimated cost per query
- total evaluation cost

This can later support comparisons between:

- free development model
- paid model
- different vendors

The final deployment model should be chosen with evidence, not only price lists.

---

## 13. Evaluation Summary Table

README should eventually include a table like:

| Metric | Result |
|---|---:|
| Guardrail Accuracy | TBD |
| All-Required-Tables Recall@4 | TBD |
| Initial Execution Accuracy | TBD |
| Retry Recovery Rate | TBD |
| Final Execution Accuracy | TBD |
| Median End-to-End Latency | TBD |
| Average Cost / Query | TBD |

All values remain `TBD` until computed by scripts.

---

## 14. Streamlit Demo Goals

The demo should make it obvious that this is not a generic chatbot wrapper.

A reviewer should see:

```text
Natural-language question
-> schema retrieval
-> generated SQL
-> validation
-> real database execution
-> optional repair
-> final answer
```

---

## 15. Streamlit Landing Page

Suggested title:

```text
Workforce Analytics Text-to-SQL Agent
```

Suggested description:

```text
Ask workforce and talent-management questions in natural language.
The system retrieves relevant database schemas, generates safe SQL,
executes it against DuckDB, repairs failed queries when possible,
and summarizes the result.
```

---

## 16. Sample Question Buttons

Provide several one-click examples:

- Headcount by business unit
- 2026 H1 review completion
- Promotion trend
- Leadership program impact

Example exact questions:

```text
How many active employees are in each business unit?

What was the 2026 H1 talent review completion rate?

How did promotions change from 2024 through 2026?

Did employees who completed Leadership Development programs have a higher later promotion rate?
```

---

## 17. Observable Pipeline UI

After execution, display:

```text
Guardrail
Retrieved Tables
Generated SQL
SQL Validation
Database Execution
SQL Repair Attempts
Query Result
Final Answer
```

Recommended behavior:

### Guardrail

```text
Passed
```

or a concise rejection.

### Retrieved Tables

Numbered list in reranker order.

### Generated SQL

Show with SQL syntax highlighting.

### SQL Validation

Show pass/fail.

### Execution

Show:

- success/failure
- execution time
- truncation when applicable

### Retry

Show number of SQL repair attempts.

### Query Result

Render a table.

### Final Answer

Render concise natural-language response.

---

## 18. What the UI Must Not Expose

Do not expose:

- API keys
- full secrets
- hidden chain-of-thought
- raw authorization data
- unnecessary internal stack traces

Full prompts should not be displayed by default.

---

## 19. Architecture Diagram

README and optionally Streamlit About page should show:

```text
Question
  ->
Guardrail
  ->
Embedding
  ->
FAISS
  ->
Reranker
  ->
SQL Generation
  ->
SQL Validator
  ->
DuckDB
  -> success -> Summary
  -> failure -> SQL Repair -> Validator -> DuckDB
```

Mermaid is acceptable.

---

## 20. README Presentation Order

Recommended:

1. Title
2. One-sentence value proposition
3. Demo screenshot/GIF
4. Live Demo link/button
5. Architecture
6. Example query walkthrough
7. Evaluation results
8. Technical design
9. Local setup
10. Repository structure
11. Limitations
12. Future work

Do not lead with installation commands.

---

## 21. Demo GIF

Create:

```text
assets/demo.gif
```

Show:

1. user enters a question
2. retrieved tables appear
3. generated SQL appears
4. query result appears
5. final answer appears

A recruiter should understand the project without running it locally.

---

## 22. Public Deployment

Initial target:

```text
Streamlit Community Cloud
```

The application should read secrets from the deployment environment.

Do not commit production credentials.

Because the public demo can incur external LLM cost, later deployment should support practical controls such as:

- maximum question length
- bounded SQL retries
- bounded result size
- provider request timeout
- optional per-session question cap

Do not let abuse protection overcomplicate the initial local V1.

---

## 23. Limitations Section

README should explicitly acknowledge V1 limitations:

- synthetic workforce data only
- English questions only
- six-table schema
- runtime semantic SQL critic not implemented
- exact LLM provider is configuration-driven
- no production authentication
- not designed for enterprise-scale concurrency

This is a strength, not a weakness: it demonstrates controlled scope.

---

## 24. Future Work

Possible V2 directions:

- employee-facing product event data
- larger schema
- multilingual embedding/reranking
- semantic SQL critic
- PostgreSQL adapter
- Redshift adapter
- true LangGraph human-in-the-loop
- model routing
- query caching
- retrieval fine-tuning
- richer data-quality metrics

---

## 25. Demo/Evaluation Acceptance Criteria

This layer is complete when:

- 80 SQL evaluation cases exist
- 20 Guardrail evaluation cases exist
- every SQL case has expected tables
- every SQL case has gold SQL
- gold SQL executes successfully
- retrieval metrics run
- FAISS vs reranker ablation runs
- execution accuracy runs
- SQL repair metrics run
- latency is measured
- cost/token usage is recorded when available
- Streamlit shows the observable pipeline
- README contains an example query
- README contains only measured metrics
- demo GIF or screenshots are included

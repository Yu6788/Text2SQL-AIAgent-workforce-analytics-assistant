# Evaluation

This document summarizes how the Workforce Analytics Assistant is evaluated. The goal is not to claim a large benchmark result. The goal is to show that the core Text-to-SQL agent workflow is testable, inspectable, and reproducible.

For architecture details, see `ENGINEERING_ARCHITECTURE.md`. For dataset details, see `DATA_GUIDE.md`.

## 1. Evaluation Goals

The evaluation layer checks whether the system can:

- Retrieve the right schema tables for a workforce question.
- Generate SQL that passes safety validation.
- Execute SQL against DuckDB without write access.
- Recover from selected SQL failures through repair.
- Reject questions outside the synthetic workforce analytics scope.
- Keep the Offline Demo path deterministic and API-cost-free.

The project uses both automated tests and small seed evaluation sets. This is intentionally lightweight and appropriate for a portfolio/demo project.

## 2. What Is Evaluated

| Area | What Is Checked | Primary Files |
| --- | --- | --- |
| Data integrity | Synthetic CSVs, DuckDB tables, row-level consistency checks. | `tests/test_phase1_data.py`, `scripts/validate_data.py` |
| Schema retrieval | Required table recall for representative questions. | `tests/test_phase2_retrieval.py`, `evaluation/retrieval_smoke_questions.json` |
| Guardrail | In-scope workforce questions vs out-of-scope external questions. | `evaluation/guardrail_questions_seed.json`, `scripts/evaluate_guardrail.py` |
| SQL validation | Unsafe SQL, unauthorized tables, external access, cross joins. | `tests/test_phase3_runtime.py`, `src/atlas_workforce/sql/validator.py` |
| Workflow execution | End-to-end agent runs over the local DuckDB database. | `tests/test_phase3_runtime.py`, `scripts/run_stub_workflow.py` |
| SQL repair | Validator failure and database binder error recovery. | `evaluation/repair_questions_seed.json`, `tests/test_phase4_evaluation.py` |
| Summary quality | Stub summaries are natural-language answers, not raw rows. | `tests/test_stub_summary.py` |
| Live API adapter | Structured JSON parsing, retry behavior, and provider error handling. | `tests/test_phase3_llm_adapter.py`, `src/atlas_workforce/llm/openai_compatible.py` |

## 3. Current Test Status

The current automated test suite passes:

```text
50 passed, 1 warning
```

Command:

```bash
python3 -m pytest -q
```

The preflight check also passes:

```text
Preflight passed.
```

Command:

```bash
python3 scripts/preflight.py
```

Preflight verifies that the database, generated CSVs, vector index artifacts, metadata YAML files, prompts, and configured LLM settings are present.

## 4. Evaluation Datasets

The repository includes small seed datasets under `evaluation/`.

### Text-To-SQL Seed Questions

File:

```text
evaluation/questions_seed.json
```

This set contains 10 representative questions:

- Active headcount.
- Headcount by business unit.
- Largest organization by active headcount.
- Talent review completion rate.
- Average performance rating by business unit.
- Development program completion rate.
- Q2 2026 promotion count.
- Annual internal mobility trend.
- Promotion rate by business unit.
- Leadership Development completion and later promotion correlation.

Each case includes:

```text
id
question
difficulty
category
expected_tables
gold_sql
notes
```

### Retrieval Smoke Questions

File:

```text
evaluation/retrieval_smoke_questions.json
```

This set checks whether the RAG pipeline retrieves the required schema tables for representative questions.

### Guardrail Questions

File:

```text
evaluation/guardrail_questions_seed.json
```

This set includes 10 questions: 5 expected in-scope workforce analytics questions and 5 expected out-of-scope questions.

### Repair Questions

File:

```text
evaluation/repair_questions_seed.json
```

This set includes two deterministic repair demos:

- Unauthorized table repair.
- Hallucinated column repair.

## 5. Current Evaluation Snapshot

These results use the local deterministic stack:

```text
StubLLMService
HashingEmbedder
LexicalReranker
DuckDB
SQLGlot validator
```

### Retrieval Smoke

Command:

```bash
python3 scripts/evaluate_retrieval.py \
  --embedding-backend hashing \
  --reranker-backend lexical \
  --index-dir data/faiss_index
```

Current result:

| Metric | Result |
| --- | ---: |
| Average Table Recall@4 | 1.000 |
| All-Required-Tables Recall@4 | 1.000 |
| Cases | 4 |

Interpretation:

The lightweight RAG stack retrieves all required schema tables for the representative smoke set.

### Guardrail Evaluation

Command:

```bash
python3 scripts/evaluate_guardrail.py \
  --output evaluation/reports/guardrail_stub_report.json
```

Current result:

| Metric | Result |
| --- | ---: |
| Guardrail Accuracy | 1.000 |
| Cases | 10 |

Interpretation:

The deterministic guardrail correctly separates supported workforce analytics questions from unrelated questions in the seed set.

### Repair Evaluation

Command:

```bash
python3 scripts/evaluate_sql.py \
  --llm-provider stub \
  --embedding-backend hashing \
  --reranker-backend lexical \
  --questions evaluation/repair_questions_seed.json \
  --output evaluation/reports/repair_stub_report.json
```

Current result:

| Metric | Result |
| --- | ---: |
| Average Table Recall@4 | 1.000 |
| All-Required-Tables Recall@4 | 1.000 |
| Execution Success Rate | 1.000 |
| Execution Accuracy | 1.000 |
| Retry Recovery Rate | 1.000 |
| Cases With SQL Retries | 2 |
| Cases | 2 |

Interpretation:

The repair loop recovers from the two deterministic repair scenarios and produces results equivalent to the gold SQL.

### Seed Text-To-SQL Evaluation In Offline Stub Mode

Command:

```bash
python3 scripts/evaluate_sql.py \
  --llm-provider stub \
  --embedding-backend hashing \
  --reranker-backend lexical \
  --questions evaluation/questions_seed.json \
  --output evaluation/reports/seed_stub_report.json
```

Current result:

| Metric | Result |
| --- | ---: |
| Average Table Recall@4 | 1.000 |
| All-Required-Tables Recall@4 | 1.000 |
| Execution Success Rate | 0.600 |
| Execution Accuracy | 0.300 |
| Cases | 10 |

Interpretation:

This result is expected for Offline Demo mode. The local stub is intentionally narrow and deterministic. It supports the main demo paths and selected repair cases, but it is not meant to solve every seed question like a general LLM.

The result is useful because it separates two things:

- Retrieval is working across the seed set.
- The deterministic stub only covers a fixed subset of natural-language SQL generation patterns.

Live API mode is the broader Text-to-SQL path.

## 6. Homepage Offline Demo Coverage

The four main homepage examples are covered by automated runtime tests and pass in Offline Demo mode:

```text
How many active employees are in each business unit?
Which organization has the highest active headcount?
What was the 2026 H1 talent review completion rate?
Which business unit had the best 2026 H1 reviews?
```

These are tested in:

```text
tests/test_phase3_runtime.py
```

This matters because a first-time user can click the visible example questions without needing API access.

## 7. Live API Evaluation Status

Live API mode has been smoke-tested on the main demo questions using a configured OpenAI-compatible provider.

The project does not currently claim a large Live API benchmark because:

- API quality depends on the configured provider and model.
- Cost and rate limits can vary.
- The current portfolio goal is transparent workflow demonstration, not leaderboard-style benchmarking.

A future Live API benchmark could reuse `evaluation/questions_seed.json` and measure:

- Execution success rate.
- Execution accuracy against gold SQL.
- SQL repair recovery rate.
- Latency.
- Provider error rate.
- Cost per query.

## 8. Metrics Definitions

### Table Recall@4

The fraction of expected tables that appear in the top 4 retrieved schema documents.

### All-Required-Tables Recall@4

Whether every expected table appears in the top 4 retrieved schema documents.

### Execution Success Rate

The fraction of cases that produce a database result.

### Execution Accuracy

The fraction of cases where generated query results are equivalent to gold SQL results.

### Retry Recovery Rate

For cases that trigger SQL repair, the fraction that recover and produce a database result.

### Guardrail Accuracy

The fraction of guardrail cases where the predicted allowed/rejected label matches the expected label.

## 9. Known Evaluation Limits

Current limits:

- The seed set is small.
- The dataset is synthetic.
- Offline Demo uses deterministic SQL rules, not broad model reasoning.
- Live API mode is not yet benchmarked across a large question set.
- Evaluation focuses on execution and table retrieval, not subjective answer style.
- English questions only.

These limits are acceptable for the current project scope, but they should be addressed before presenting this as a production-grade Text-to-SQL benchmark.

## 10. Reproducible Commands

Run all tests:

```bash
python3 -m pytest -q
```

Run preflight:

```bash
python3 scripts/preflight.py
```

Run retrieval smoke evaluation:

```bash
python3 scripts/evaluate_retrieval.py \
  --embedding-backend hashing \
  --reranker-backend lexical \
  --index-dir data/faiss_index
```

Run guardrail evaluation:

```bash
python3 scripts/evaluate_guardrail.py \
  --output evaluation/reports/guardrail_stub_report.json
```

Run repair evaluation:

```bash
python3 scripts/evaluate_sql.py \
  --llm-provider stub \
  --embedding-backend hashing \
  --reranker-backend lexical \
  --questions evaluation/repair_questions_seed.json \
  --output evaluation/reports/repair_stub_report.json
```

Run seed Text-to-SQL evaluation in Offline Demo mode:

```bash
python3 scripts/evaluate_sql.py \
  --llm-provider stub \
  --embedding-backend hashing \
  --reranker-backend lexical \
  --questions evaluation/questions_seed.json \
  --output evaluation/reports/seed_stub_report.json
```

## 11. Evaluation Takeaway

The current evaluation shows that the project has a reliable, inspectable demo path:

- Tests pass.
- Preflight passes.
- Schema retrieval works on the smoke set.
- Guardrails work on the seed set.
- SQL repair works on deterministic repair cases.
- Homepage Offline Demo examples are covered.

The evaluation also honestly shows the current boundary:

```text
Offline Demo is deterministic and narrow.
Live API mode is broader, but not yet benchmarked at scale.
```

That is the right evaluation posture for this version of the project.

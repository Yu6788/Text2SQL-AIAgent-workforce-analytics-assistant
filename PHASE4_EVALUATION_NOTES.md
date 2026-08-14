# Phase 4 Evaluation Foundation

## Implemented

- Seed SQL evaluation set:
  - `evaluation/questions_seed.json`
  - 10 cases across easy, medium, and hard categories
  - each case has `expected_tables` and executable `gold_sql`
- Result normalization and comparison helpers
- Evaluation runner:
  - executes gold SQL against DuckDB
  - runs the workflow
  - computes retrieval Recall@4
  - computes all-required-tables Recall@4
  - computes execution success rate
  - records SQL retry count and retry history
  - computes retry recovery rate
  - compares generated result to gold result
  - records per-case latency
- CLI:

```bash
python3 scripts/evaluate_sql.py \
  --llm-provider stub \
  --embedding-backend hashing \
  --reranker-backend lexical \
  --output evaluation/reports/seed_stub_report.json
```

## Stub Smoke Result

The deterministic stub LLM only supports a small set of hard-coded questions,
so execution accuracy is intentionally limited. The useful check here is that
the evaluator, gold SQL, retrieval stack, and result comparison all run.

Observed seed report:

```text
total_cases: 10
average_table_recall_at_4: 1.000
all_required_tables_recall_at_4: 1.000
execution_success_rate: 0.300
execution_accuracy: 0.300
```

## Repair Smoke Result

Run:

```bash
python3 scripts/evaluate_sql.py \
  --questions evaluation/repair_questions_seed.json \
  --llm-provider stub \
  --embedding-backend hashing \
  --reranker-backend lexical \
  --output evaluation/reports/repair_stub_report.json
```

Observed repair report:

```text
total_cases: 2
execution_success_rate: 1.000
execution_accuracy: 1.000
retry_recovery_rate: 1.000
cases_with_sql_retries: 2
```

## Running With Configured Real Provider

After API quota is available, run:

```bash
python3 scripts/evaluate_sql.py \
  --llm-provider configured \
  --embedding-backend sentence-transformers \
  --reranker-backend cross-encoder \
  --output evaluation/reports/seed_configured_report.json
```

The current free-tier Gemini key previously hit HTTP 429 quota, so the first
full configured-provider run should wait until the quota window resets or use
a more stable provider/key.

## Verification

```text
python3 -m pytest -q
38 passed
```

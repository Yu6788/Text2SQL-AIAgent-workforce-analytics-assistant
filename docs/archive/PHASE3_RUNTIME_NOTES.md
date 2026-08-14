# Phase 3 Runtime Foundation

## Implemented

- Typed settings loader for `config.yaml`
- Versioned prompt files under `src/atlas_workforce/prompts/`
- Provider-agnostic LLM service protocol
- Deterministic local `StubLLMService` for offline smoke runs
- OpenAI-compatible LLM adapter for providers exposing `/chat/completions`
- `.env`-based LLM provider configuration
- SQLGlot-based SQL validator
- Read-only DuckDB executor with result truncation detection
- Retrieval-aware LangGraph workflow:
  - Guardrail
  - BGE/FAISS schema retrieval
  - Reranker Top-4 schema context selection
  - SQL generation
  - SQL validation
  - DuckDB execution
  - SQL repair loop
  - Summary
- Provider errors are captured as `API_ERROR` states instead of exposing stack
  traces in normal workflow output.
- CLI smoke runner:

```bash
python3 scripts/run_workflow.py \
  "How many active employees are in each business unit?"
```

The older `scripts/run_stub_workflow.py` remains available for deterministic
local-only smoke runs.

## LLM Provider Configuration

Default `config.yaml` uses the local stub:

```yaml
llm:
  provider: stub
  model: deterministic_sql_rules_v1
```

To use an OpenAI-compatible provider, create `.env` locally:

```env
LLM_PROVIDER=openai_compatible
LLM_MODEL=<model-id>
LLM_API_KEY=<api-key>
LLM_BASE_URL=<provider-base-url>
```

OpenRouter can use:

```env
LLM_PROVIDER=openrouter
LLM_MODEL=<openrouter-model-id>
LLM_API_KEY=<api-key>
LLM_BASE_URL=https://openrouter.ai/api/v1
```

OpenAI can use:

```env
LLM_PROVIDER=openai
LLM_MODEL=<openai-model-id>
LLM_API_KEY=<api-key>
LLM_BASE_URL=https://api.openai.com/v1
```

## Verified Smoke Behavior

Answerable workforce question:

```text
status: SUCCESS
guardrail: True
retrieved_tables:
1. employees
2. organizations
3. employee_programs
4. talent_reviews
```

Unrelated question:

```text
status: REJECTED_BY_GUARDRAIL
guardrail: False
```

## Current Boundaries

- The LLM provider remains intentionally TBD.
- The stub LLM is only for deterministic local testing and demo plumbing.
- Runtime semantic SQL correctness is not judged by the validator; it belongs
  to the evaluation layer.
- DuckDB 1.4.5 in this local environment does not recognize
  `statement_timeout`, so the executor currently enforces read-only mode and
  result truncation but not a database-level timeout.
- The current Gemini free-tier key hit HTTP 429 quota after successful smoke
  verification. The workflow now reports this as `API_ERROR`.

## Verification

```text
python3 -m pytest -q
25 passed
```

# Detailed Product And Technical Guide

This guide explains what the Workforce Analytics Assistant does, how to explore it, which questions to ask, and what technical details to inspect.

Use this document when sharing the project with reviewers, interviewers, classmates, or collaborators who want more than a quick README.

## 1. Product Summary

The Workforce Analytics Assistant is a Text-to-SQL agent for synthetic workforce analytics. A user asks a workforce question in natural language, and the system turns that question into SQL, validates the SQL, executes it against a local DuckDB database, and summarizes the result in natural language.

Live app:

```text
https://text2sql-aiagent-workforce-analytics-assistant-8phrvf5mmjdmxrb.streamlit.app/
```

GitHub repo:

```text
https://github.com/Yu6788/Text2SQL-AIAgent-workforce-analytics-assistant
```

The project is designed to show:

- Product thinking: a usable analytics assistant rather than a raw script.
- Agentic workflow: guardrail, retrieval, generation, validation, execution, repair, and summary.
- Data engineering: synthetic workforce data, DuckDB, table metadata, metric definitions.
- Responsible boundaries: synthetic data only, read-only SQL, no protected attributes or private employee records.
- Evaluation mindset: tests, stub mode, API mode, repair demos, and guardrail examples.

## 2. What I Built

The project includes four major layers.

### Streamlit Product Interface

The app provides a dark-themed analytics workspace with:

- A chat-style `Conversation` interface.
- Example workforce questions under `What can I ask?`.
- `Offline Demo` and `Live API` run modes.
- Current-session follow-up support.
- Expandable workflow details under each answer.
- Sidebar documentation for agent scope, tables, metrics, context, and limits.

### Agentic Text-to-SQL Backend

The backend follows a structured workflow:

```text
User question
  -> Guardrail
  -> Schema retrieval
  -> SQL generation
  -> SQL validation
  -> DuckDB execution
  -> SQL repair, if needed
  -> Natural-language summary
```

This is not just a single prompt. The intermediate steps are preserved and shown in the UI.

### Synthetic Workforce Dataset

The project uses a synthetic workforce analytics database covering 2024-2026. It includes:

- `employees`
- `organizations`
- `talent_reviews`
- `development_programs`
- `employee_programs`
- `internal_moves`

The data is generated and included for demo stability. No real employee, company, salary, protected attribute, or PII data is used.

### Evaluation And Demo Assets

The repository includes:

- Unit and integration tests.
- Guardrail test cases.
- Retrieval smoke questions.
- SQL evaluation seeds.
- Repair demo questions.
- Demo checklist and architecture notes.

Current local test status:

```text
50 passed, 1 warning
```

## 3. How To Use The Live App

Open the app:

```text
https://text2sql-aiagent-workforce-analytics-assistant-8phrvf5mmjdmxrb.streamlit.app/
```

### Step 1: Choose A Run Mode

In the left sidebar, choose one of:

```text
Offline Demo
Live API
```

Use `Offline Demo` when:

- You want a cost-free deterministic demo.
- You want to test supported fixed examples.
- You want no external model call.

Use `Live API` when:

- You want the configured LLM provider to generate SQL.
- You want broader question coverage.
- You want a more realistic Text-to-SQL demo.

### Step 2: Ask A Question

You can either:

- Click one of the example questions under `What can I ask?`.
- Type your own question in the input box.
- Press `Send`.

The assistant will first show `Thinking...`, then produce a natural-language answer.

### Step 3: Inspect Workflow Details

After an answer appears, click:

```text
Show workflow details
```

Use this section to inspect:

- Context and guardrail status.
- Retrieved tables.
- Generated SQL.
- SQL validation result.
- DuckDB database result.
- SQL repair attempts.

This is the best place to show that the product is an agentic system, not just a chatbot.

### Step 4: Ask A Follow-Up

After a full first question, ask a short follow-up such as:

```text
What about Technology?
```

or:

```text
Show percentages instead.
```

The app uses the previous turn's state to resolve lightweight follow-ups in the current session.

Use `Clear chat` to reset the conversation.

## 4. Recommended Demo Script

Use this exact flow for a polished demo.

### Demo Part A: Headcount Analytics

Ask:

```text
How many active employees are in each business unit?
```

What to show:

- The natural-language answer appears directly in chat.
- The user does not need to read SQL to understand the result.
- `Show workflow details` reveals retrieved tables and generated SQL.

Then ask:

```text
What about Technology?
```

What to show:

- The app supports a short follow-up after a full initial question.
- The assistant resolves the follow-up from the previous context.

### Demo Part B: Organization Ranking

Ask:

```text
Which organization has the highest active headcount?
```

What to show:

- Live API can generate a more specific aggregation query.
- SQL joins `employees` and `organizations`.
- The result is summarized as a concise answer.

### Demo Part C: Talent Review Metric

Ask:

```text
What was the 2026 H1 talent review completion rate?
```

What to show:

- The app understands metric-style workforce questions.
- The SQL uses `talent_reviews`.
- The result is expressed as a completion rate.

Note: `H1` means the first half of the year, January 1 through June 30.

### Demo Part D: Review Quality By Business Unit

Ask:

```text
Which business unit had the best 2026 H1 reviews?
```

What to show:

- Live API can infer that "best reviews" means ranking by review outcome.
- The query uses employee and organization context with talent reviews.

### Demo Part E: Guardrail Boundary

Ask:

```text
What is the weather today?
```

What to show:

- The system rejects out-of-scope questions.
- No SQL should be generated for external facts.
- This demonstrates product boundaries and safer behavior.

## 5. What Questions Users Can Ask

Best-fit questions are aggregate workforce analytics questions.

### Headcount

Try:

```text
How many active employees are in each business unit?
Which organization has the highest active headcount?
What percentage of active employees is in each business unit?
```

Relevant tables:

- `employees`
- `organizations`

### Talent Reviews

Try:

```text
What was the 2026 H1 talent review completion rate?
Which business unit had the best 2026 H1 reviews?
Which business unit had the highest average performance rating in 2026 H1?
```

Relevant tables:

- `talent_reviews`
- `employees`
- `organizations`

### Development Programs

Try:

```text
Which development program had the highest completion rate?
Did Leadership Development completion correlate with later promotions?
```

Relevant tables:

- `development_programs`
- `employee_programs`
- `internal_moves`
- `employees`

### Mobility And Promotions

Try:

```text
How many employees were promoted in Q2 2026?
What was the annual internal mobility trend from 2024 through 2026?
```

Relevant tables:

- `internal_moves`
- `employees`
- `organizations`

Note: Mobility questions are better suited to `Live API` mode. `Offline Demo` intentionally supports only a smaller deterministic set.

## 6. What Users Should Not Ask

The app is intentionally scoped. These are out of scope:

```text
What is the weather today?
What is the current Bitcoin price?
Show me employee salaries.
List employee names and emails.
Analyze gender differences in promotions.
Give me legal advice about performance reviews.
```

Reasons:

- The app has no external internet or market data.
- The dataset is synthetic and does not contain real personal records.
- Private employee lookups and protected attributes are not part of the demo.
- The product is an analytics demo, not legal or HR policy advice.

## 7. How To Interpret The Workflow Details

Each answer has an expandable workflow section.

### Context

Shows high-level workflow context, including:

- Whether the question was allowed.
- Whether it was treated as a follow-up.
- The resolved question when applicable.
- Pipeline status.

Use this to explain how the agent keeps the run inspectable.

### Retrieved Tables

Shows which table metadata was selected as relevant.

Why this matters:

- Text-to-SQL quality depends on grounding the model in the right schema.
- The retrieval step helps avoid sending irrelevant table context.
- Reviewers can see whether the agent selected the right tables.

### Generated SQL

Shows the SQL produced by the model or deterministic stub.

Why this matters:

- The user can inspect exactly how the natural-language question was translated.
- This makes the assistant more transparent than a black-box answer.

### Validation

Shows whether the SQL passed safety and structure checks.

The validator helps enforce:

- Read-only query behavior.
- Known table and column usage.
- SQL dialect compatibility.
- No unsafe write operations.

### Database Result

Shows the DuckDB result returned by the SQL query.

Why this matters:

- The answer is grounded in actual query output.
- Reviewers can compare the SQL result with the natural-language summary.

### Repair

Shows bounded SQL repair attempts.

Why this matters:

- If SQL generation fails validation or execution, the app can attempt repair.
- Repair attempts are limited, not infinite.
- The user can inspect what happened.

## 8. Offline Demo Vs Live API

### Offline Demo

Offline Demo uses deterministic local rules.

Pros:

- No API key required.
- No API cost.
- Stable for specific known questions.
- Good for showing the pipeline without relying on model availability.

Limits:

- It does not cover every possible user question.
- It is intentionally narrow.
- Some natural questions may return no answer in Offline Demo.

Good Offline Demo questions:

```text
How many active employees are in each business unit?
What was the 2026 H1 talent review completion rate?
Which development program had the highest completion rate?
Did Leadership Development completion correlate with later promotions?
What percentage of active employees is in each business unit?
```

### Live API

Live API uses the configured OpenAI-compatible model provider.

Pros:

- Broader natural-language coverage.
- More realistic SQL generation.
- Better for open-ended exploration.

Limits:

- Requires a configured API key.
- May incur provider cost.
- Quality depends on the model and prompt behavior.
- Model output still needs validation and inspection.

## 9. Technical Architecture

The main app entrypoint is:

```text
app.py
```

Core backend code lives under:

```text
src/atlas_workforce/
```

Important modules:

```text
src/atlas_workforce/runtime.py
src/atlas_workforce/graph/workflow.py
src/atlas_workforce/llm/service.py
src/atlas_workforce/llm/openai_compatible.py
src/atlas_workforce/rag/retrieval.py
src/atlas_workforce/sql/validator.py
src/atlas_workforce/sql/executor.py
```

### Runtime

`runtime.py` wires together the services:

- LLM service.
- SQL validator.
- DuckDB executor.
- Business context.
- Schema documents.
- Retrieval and reranking components.

### Workflow

`graph/workflow.py` defines the graph-style execution flow. Each node updates shared state and passes it forward.

### LLM Service

The project has two LLM paths:

- `StubLLMService` for Offline Demo.
- `OpenAICompatibleLLMService` for Live API mode.

The OpenAI-compatible adapter can work with providers that expose a compatible chat completions API.

### Retrieval

The demo uses a lightweight hashing embedder and lexical reranker in the Streamlit app for fast deployment. Optional production-style dependencies are listed separately in:

```text
requirements-optional.txt
```

These optional dependencies support:

- `sentence-transformers`
- `faiss-cpu`
- cross-encoder reranking experiments

### SQL Validation

The SQL validator uses SQL parsing to check generated SQL before execution.

It helps prevent:

- Write operations.
- Unknown table usage.
- Invalid columns.
- Unsupported or unsafe SQL patterns.

### DuckDB Execution

Queries run against:

```text
data/atlas_workforce.duckdb
```

Execution is read-only and result-capped for demo safety.

## 10. Data Model

The dataset is organized around employees, organizations, reviews, programs, enrollments, and moves.

```text
organizations
     ^
     |
employees
  ^   ^   ^
  |   |   |
  |   |   +---------------- internal_moves
  |   |
  |   +-------------------- employee_programs
  |                              |
  |                              v
  |                       development_programs
  |
  +------------------------ talent_reviews
```

Table summaries:

- `employees`: employment status, hire dates, job information, organization assignment.
- `organizations`: organization names, business units, regions, leaders, status.
- `talent_reviews`: review cycles, completion status, performance ratings, potential ratings.
- `development_programs`: program catalog, program type, target job level.
- `employee_programs`: enrollments, completion status, completion dates, scores.
- `internal_moves`: promotions, transfers, role changes, mobility events.

## 11. Local Setup

Install core dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Run the app:

```bash
streamlit run app.py
```

Run tests:

```bash
python3 -m pytest -q
```

Optional production-style retrieval dependencies:

```bash
python3 -m pip install -r requirements-optional.txt
```

## 12. Live API Setup

For local development, create a `.env` file:

```env
LLM_PROVIDER=openai_compatible
LLM_MODEL=<model-id>
LLM_API_KEY=<your-api-key>
LLM_BASE_URL=<provider-base-url>
```

For Streamlit Community Cloud, use TOML secrets:

```toml
LLM_PROVIDER = "openai_compatible"
LLM_MODEL = "<model-id>"
LLM_API_KEY = "<your-api-key>"
LLM_BASE_URL = "<provider-base-url>"
```

Do not commit real API keys.

## 13. Deployment

The app is deployed through Streamlit Community Cloud.

Deployment settings:

```text
Repository: Yu6788/Text2SQL-AIAgent-workforce-analytics-assistant
Branch: main
Main file path: app.py
Python version: 3.11 or 3.12 recommended
```

Required files:

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

Secrets template:

```text
streamlit_secrets.example.toml
```

## 14. Suggested Exploration Checklist

Use this checklist to fully explore the product.

### Basic Product Flow

- Open the live app.
- Run one example question.
- Confirm the answer appears under the question.
- Open `Show workflow details`.
- Inspect generated SQL and database result.

### Conversation Flow

- Ask a full first question.
- Ask a short follow-up.
- Confirm the assistant resolves the follow-up.
- Click `Clear chat`.
- Confirm the conversation resets.

### Agent Transparency

- Check retrieved tables.
- Check generated SQL.
- Check validation result.
- Check database result.
- Check repair tab.

### Boundary Testing

- Ask an out-of-scope question.
- Confirm the guardrail rejects it.
- Confirm no SQL result is produced.

### Live API Testing

- Switch to `Live API`.
- Ask a main example question.
- Ask a more natural variation.
- Confirm validation and execution still pass.

## 15. Known Limits

This is a portfolio/demo project, not a production HR analytics system.

Known limits:

- English questions only.
- Synthetic six-table schema only.
- Current-session memory only.
- No long-term conversation persistence.
- Offline Demo supports a fixed deterministic subset.
- Live API quality depends on the configured provider.
- No external facts, current events, weather, or market data.
- No real private employee records or protected attributes.

## 16. Best Way To Review The Project

For non-technical reviewers:

1. Open the live app.
2. Ask the main example questions.
3. Try one follow-up.
4. Read the sidebar `Info` section.

For technical reviewers:

1. Inspect `README.md`.
2. Read this detailed guide.
3. Run the tests.
4. Review `src/atlas_workforce/graph/workflow.py`.
5. Review `src/atlas_workforce/sql/validator.py`.
6. Review `src/atlas_workforce/llm/openai_compatible.py`.
7. Use `Show workflow details` in the UI to connect the code path to the product experience.

## 17. One-Minute Pitch

This project is a synthetic workforce analytics assistant that turns natural language into validated SQL and grounded answers. It is designed as a transparent Text-to-SQL agent: users can ask business questions, see the final answer immediately, and inspect retrieval, SQL generation, validation, execution, and repair details. The app supports both a free deterministic Offline Demo and a broader Live API mode, with clear data and privacy boundaries.

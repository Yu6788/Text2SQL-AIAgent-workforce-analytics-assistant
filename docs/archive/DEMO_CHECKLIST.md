# Demo Checklist

Use the Streamlit app locally:

```bash
streamlit run app.py
```

Local URL:

```text
http://127.0.0.1:8501
```

## Stub Mode

Keep `LLM mode = Stub`.

### Happy Path

Question:

```text
How many active employees are in each business unit?
```

Expected:

- status is `SUCCESS`
- guardrail is allowed
- retrieved tables include `employees` and `organizations`
- SQL validation passes
- database result table appears
- final answer appears

### Repair Path: Validator Failure

Question:

```text
Repair demo unsafe: how many active employees are there?
```

Expected:

- status is `SUCCESS`
- SQL retries is `1`
- repair tab shows unauthorized table failure
- final repaired query returns active employee count

### Repair Path: Database Failure

Question:

```text
Repair demo bad column: count employees by employment status.
```

Expected:

- status is `SUCCESS`
- SQL retries is `1`
- repair tab shows bad column or binder error
- final repaired query returns counts by employment status

### Guardrail Rejection

Question:

```text
What is the weather today?
```

Expected:

- status is `REJECTED_BY_GUARDRAIL`
- no SQL is generated
- no database result is shown

## Configured Provider Mode

Use only when `.env` is configured and API quota is available.

Question:

```text
What was the 2026 H1 talent review completion rate?
```

Expected:

- status is `SUCCESS`, or `API_ERROR` if provider quota is exhausted
- provider errors appear as friendly workflow errors, not Python tracebacks

### Follow-Up Context

The app supports lightweight session-level follow-up questions. During the
current browser session, the UI keeps visible chat turns in `st.session_state`
and passes the previous agent state into the next run.

This means short follow-ups such as:

```text
What about Technology?
```

can be resolved from the immediately previous question, SQL, and answer.

Current boundary:

- the visible chat history is kept for the current Streamlit session
- `Clear chat` resets the visible chat and follow-up context
- the resolver uses the previous turn's question, SQL, and answer
- the app does not persist long-term chat history
- the app does not send the full multi-turn transcript into every prompt

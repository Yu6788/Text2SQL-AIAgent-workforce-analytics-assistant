# Business Narrative

This document explains the business meaning of the Workforce Analytics Assistant. It focuses on why this project matters from a product, analytics, and decision-support perspective.

For technical architecture, see `ENGINEERING_ARCHITECTURE.md`. For data details, see `DATA_GUIDE.md`. For evaluation details, see `EVALUATION.md`.

## 1. Business Problem

Workforce analytics teams often sit between business leaders and complex HR data.

Business users may ask questions such as:

```text
How many active employees are in each business unit?
What was the talent review completion rate?
Which development program had the highest completion rate?
Did Leadership Development completion correlate with later promotions?
```

These questions sound simple, but answering them usually requires:

- Knowing which tables contain the right data.
- Understanding business metric definitions.
- Writing joins across employee, organization, review, program, and mobility tables.
- Applying the right filters and denominators.
- Validating that the SQL is safe and correct.
- Turning raw query results into a concise business answer.

In many organizations, this creates a gap:

```text
Business user has the question
Analytics team has the data and SQL skills
Decision-making waits in between
```

The Workforce Analytics Assistant explores how an AI agent can reduce that gap.

## 2. Product Idea

The product idea is a natural-language analytics assistant for workforce questions.

Instead of asking users to write SQL or search through schema documentation, the assistant lets them ask a question in plain English. The system then:

```text
understands the workforce question
retrieves relevant schema context
generates SQL
validates the SQL
executes the query
summarizes the result
shows the workflow details
```

The goal is not to replace analysts. The goal is to make common aggregate workforce questions faster, more transparent, and easier to explore.

## 3. Why Workforce Analytics Is A Good Use Case

Workforce analytics is a strong domain for Text-to-SQL because many valuable questions are structured, metric-driven, and grounded in relational data.

Common business questions include:

- Headcount by business unit, organization, region, or job family.
- Review completion and performance outcomes.
- Development program participation and completion.
- Promotions, transfers, and internal mobility trends.
- Correlations between development programs and later career movement.

These questions usually require multiple tables but still have clear data boundaries. That makes the domain suitable for a controlled AI assistant with:

- Synthetic data boundaries.
- Table-level schema retrieval.
- SQL validation.
- Read-only execution.
- Inspectable intermediate steps.

## 4. Business Value

### Faster Access To Workforce Insights

A manager or HR partner can ask a natural-language question and receive an immediate answer instead of waiting for a manually written query.

Example:

```text
Question:
Which business unit had the best 2026 H1 reviews?

Answer:
Sales had the best 2026 H1 reviews, with an average performance rating of 3.25 across 342 completed reviews.
```

This shortens the path from question to insight.

### Lower Barrier For Non-Technical Users

Many business users understand the question they want to ask but do not know:

- table names
- primary keys
- foreign keys
- SQL syntax
- metric denominator rules

The assistant hides that complexity while still keeping the underlying SQL available for inspection.

### More Transparent AI Analytics

The assistant does not only return an answer. It shows:

- retrieved tables
- generated SQL
- validation status
- database result
- repair attempts

This matters because business analytics requires trust. A black-box answer is less useful than an answer whose data path can be inspected.

### Safer Exploration

The workflow includes guardrails and SQL validation before database execution.

This supports a safer pattern:

```text
natural-language question
-> scope check
-> schema grounding
-> SQL validation
-> read-only execution
```

That is important for analytics domains where users may ask sensitive or out-of-scope questions.

### Better Analyst Leverage

The assistant can handle repeatable, aggregate, first-pass questions. Analysts can then focus on:

- metric design
- data quality
- deeper investigation
- stakeholder interpretation
- strategic recommendations

The product acts as an analytics accelerator, not a replacement for human judgment.

## 5. Example Business Scenario

Imagine an HR business partner preparing for a leadership meeting.

They want to understand workforce health across the company:

1. Which business units have the largest active headcount?
2. Did the 2026 H1 review cycle complete on time?
3. Which business unit had the strongest review outcomes?
4. Which development programs are completing successfully?
5. Are Leadership Development completers promoted at a different rate later?

Without an assistant, this may require several analyst requests or manual SQL queries.

With the assistant, the user can explore these questions conversationally:

```text
How many active employees are in each business unit?
What about Technology?
Show percentages instead.
Which business unit had the best 2026 H1 reviews?
Did Leadership Development completion correlate with later promotions?
```

The user receives immediate answers and can inspect the pipeline behind each answer.

## 6. Decision Support, Not Decision Automation

This project is intentionally positioned as decision support.

It can help users:

- explore aggregate workforce patterns
- compare business units
- inspect metric calculations
- identify areas for follow-up analysis
- understand how a SQL-backed answer was produced

It should not be used to:

- make real employment decisions
- evaluate individual employees
- infer protected attributes
- make compensation decisions
- replace HR policy or legal review

This distinction is important. The assistant supports analysis, but humans remain responsible for interpretation and action.

## 7. Why Synthetic Data Matters

The project uses synthetic workforce data because workforce analytics can involve sensitive information.

Using synthetic data allows the project to demonstrate:

- realistic table relationships
- realistic metric patterns
- realistic Text-to-SQL workflow complexity
- privacy-safe public deployment

The project can be shared on GitHub and Streamlit without exposing real employees, salaries, protected attributes, or private company records.

## 8. Why Inspectability Matters

In business analytics, the answer alone is not enough.

Users and reviewers need to know:

- Which tables were used?
- Was the SQL valid?
- Was the database actually queried?
- Was the result summarized from rows?
- Did the system repair a failed query?

This project makes those steps visible through `Show workflow details`.

That design choice supports trust and makes the product more credible than a simple chatbot interface.

## 9. Potential Stakeholders

A product like this could be useful to:

- HR business partners
- people analytics teams
- workforce planning teams
- talent management teams
- finance/workforce planning partners
- operations leaders
- data analysts supporting HR stakeholders

Each group benefits from faster access to aggregate workforce questions while still preserving analyst oversight and data boundaries.

## 10. Business Metrics Supported

The current synthetic data model supports metrics such as:

- active headcount
- review completion rate
- average performance rating
- program completion rate
- promotion rate
- internal mobility rate
- Leadership Development completion and later promotion correlation

These metrics are useful because they connect to common workforce planning and talent management questions:

```text
Where is the workforce concentrated?
Are review processes being completed?
Which programs appear effective?
Where are promotions and moves happening?
Are development investments associated with later mobility?
```

## 11. Product Boundaries

The assistant is strongest for:

- aggregate analytics
- synthetic workforce data
- English-language questions
- questions answerable from the six-table schema
- inspectable SQL-backed answers

The assistant is not designed for:

- private employee records
- salary or compensation analytics
- protected attribute analysis
- external facts
- legal or HR policy advice
- production HR decision automation

Clear boundaries make the product safer and easier to explain.

## 12. Business Takeaway

The Workforce Analytics Assistant demonstrates how agentic Text-to-SQL can turn workforce data into accessible, inspectable business answers.

The business value is not only that the system can generate SQL. The value is that it connects:

```text
business question
-> trusted data context
-> validated query
-> grounded result
-> readable answer
-> inspectable workflow
```

That is the core product story: faster workforce insight, lower technical barrier, and more transparent AI-assisted analytics.

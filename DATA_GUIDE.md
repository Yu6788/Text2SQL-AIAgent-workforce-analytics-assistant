# Data Guide

This guide explains the synthetic workforce analytics dataset behind the Workforce Analytics Assistant. It covers what the data represents, how the tables relate to each other, which business metrics are supported, and what users can safely ask.

For product usage, see `DETAILED_INSTRUCTIONS.md`. For agent architecture, see `ENGINEERING_ARCHITECTURE.md`.

## 1. Dataset Overview

The project uses a synthetic workforce and talent-management dataset. It is designed for aggregate analytics, Text-to-SQL generation, schema retrieval, SQL validation, and demoable workforce questions.

The core analytics period is:

```text
2024-01-01 through 2026-12-31
```

The employee table includes hire history beginning in 2018 so that active headcount and workforce tenure patterns can be represented realistically. Review, development program, and internal mobility activity is concentrated in the 2024-2026 analytics window.

Data size:

| Table | Rows | What It Represents |
| --- | ---: | --- |
| `organizations` | 50 | Synthetic organization units. |
| `employees` | 5,000 | Synthetic employee records without names or PII. |
| `talent_reviews` | 15,000 | Employee review records across 2024-2026 H1/H2 cycles. |
| `development_programs` | 40 | Workforce development programs. |
| `employee_programs` | 8,000 | Employee enrollments in development programs. |
| `internal_moves` | 3,000 | Promotions, transfers, and role changes. |

The dataset is stored in:

```text
data/atlas_workforce.duckdb
data/generated/*.csv
```

The schema metadata used by the RAG pipeline lives in:

```text
metadata/business_context.yaml
metadata/tables/*.yaml
```

## 2. Synthetic Data Boundary

This dataset is fully synthetic.

It does not contain:

- Real employees.
- Employee names.
- Emails.
- Salaries.
- Protected attributes.
- Demographic attributes.
- Private personal data.
- Real company records.

The data should be used only for product demonstration, engineering review, SQL generation, and analytics workflow testing. It should not be interpreted as real HR evidence or used for real workforce decisions.

## 3. Relationship Model

The data is organized around employees, organizations, reviews, programs, enrollments, and internal moves.

High-level relationship map:

```text
organizations
  -> employees.organization_id

employees
  -> talent_reviews.employee_id
  -> employee_programs.employee_id
  -> internal_moves.employee_id
  -> employees.manager_id

development_programs
  -> employee_programs.program_id

organizations
  -> internal_moves.from_organization_id
  -> internal_moves.to_organization_id
```

Common join paths:

```text
employees + organizations
  -> headcount by business unit, organization, region, job family

employees + talent_reviews + organizations
  -> review completion, performance ratings, potential ratings, promotion recommendations

employee_programs + development_programs
  -> program enrollment and completion analytics

employees + employee_programs + development_programs + internal_moves
  -> development program completion and later promotion correlation

employees + internal_moves + organizations
  -> mobility, promotions, transfers, and role movement trends
```

## 4. Tables

### `organizations`

Grain:

```text
One row represents one organization.
```

Primary key:

```text
organization_id
```

Important columns:

| Column | Meaning |
| --- | --- |
| `organization_id` | Unique organization identifier. |
| `organization_name` | Human-readable synthetic organization name. |
| `business_unit` | Business unit such as Technology, Operations, Sales, or People. |
| `region` | Region such as North America, Europe, Asia Pacific, or Latin America. |
| `org_leader_id` | Employee identifier for the organization leader. |
| `organization_status` | Active or Inactive organization status. |

This table supports questions about:

- Business unit structure.
- Organization-level headcount.
- Region-level grouping.
- Active versus inactive organizations.

Example question:

```text
Which organization has the highest active headcount?
```

### `employees`

Grain:

```text
One row represents one employee.
```

Primary key:

```text
employee_id
```

Foreign keys:

```text
organization_id -> organizations.organization_id
manager_id -> employees.employee_id
```

Important columns:

| Column | Meaning |
| --- | --- |
| `employee_id` | Unique synthetic employee identifier. |
| `hire_date` | Employee hire date. |
| `termination_date` | Termination date, null when not terminated. |
| `employment_status` | Active, Terminated, or Leave. |
| `job_level` | Job level from L2 through L7. |
| `job_family` | Functional job family such as Data, Product, Finance, or HR. |
| `location` | Employee work region. |
| `manager_id` | Manager employee identifier, nullable for senior employees. |
| `organization_id` | Current organization assignment. |

This table supports questions about:

- Active headcount.
- Workforce status.
- Job level distribution.
- Job family distribution.
- Location and organization assignment.
- Manager hierarchy in a limited synthetic form.

Example question:

```text
How many active employees are in each business unit?
```

### `talent_reviews`

Grain:

```text
One row represents one employee review in one review cycle.
```

Primary key:

```text
review_id
```

Foreign key:

```text
employee_id -> employees.employee_id
```

Important columns:

| Column | Meaning |
| --- | --- |
| `review_id` | Unique review identifier. |
| `employee_id` | Employee receiving the review. |
| `review_cycle` | Review cycle such as 2024_H1 or 2026_H2. |
| `review_date` | Date associated with the review cycle. |
| `performance_rating` | Rating from 1 through 5. |
| `potential_rating` | Rating from 1 through 5. |
| `promotion_recommended` | Whether the review recommended promotion. |
| `review_status` | Completed, Pending, or Cancelled. |

This table supports questions about:

- Review completion rate.
- Average performance rating.
- Average potential rating.
- Promotion recommendations.
- H1/H2 review cycle comparisons.
- Business unit review outcomes when joined to employees and organizations.

Example questions:

```text
What was the 2026 H1 talent review completion rate?
Which business unit had the best 2026 H1 reviews?
```

Note:

```text
H1 = first half of the year
H2 = second half of the year
```

### `development_programs`

Grain:

```text
One row represents one development program.
```

Primary key:

```text
program_id
```

Important columns:

| Column | Meaning |
| --- | --- |
| `program_id` | Unique program identifier. |
| `program_name` | Synthetic program name. |
| `program_type` | Category such as Leadership Development or Mentorship. |
| `start_date` | Program start date. |
| `end_date` | Program end date. |
| `target_job_level` | Intended employee job level for the program. |
| `program_status` | Planned, Active, Completed, or Cancelled. |

Program types:

```text
Leadership Development
Technical Upskilling
Mentorship
Career Development
Manager Training
```

This table supports questions about:

- Development program catalog.
- Program type comparisons.
- Program timing.
- Target job level.
- Program status.

Example question:

```text
Which development program had the highest completion rate?
```

### `employee_programs`

Grain:

```text
One row represents one employee enrollment in one program.
```

Primary key:

```text
employee_program_id
```

Foreign keys:

```text
employee_id -> employees.employee_id
program_id -> development_programs.program_id
```

Important columns:

| Column | Meaning |
| --- | --- |
| `employee_program_id` | Unique enrollment identifier. |
| `employee_id` | Employee enrolled in the program. |
| `program_id` | Development program identifier. |
| `enrollment_date` | Date the employee enrolled. |
| `completion_date` | Date completed, null if not completed. |
| `participation_status` | Enrolled, In Progress, Completed, or Withdrawn. |
| `completion_score` | Synthetic completion score, null for incomplete enrollments. |

This table supports questions about:

- Program enrollment.
- Program completion.
- Completion score.
- Participation status.
- Development program outcomes.

This table is usually joined with `development_programs` to group results by program name or program type.

### `internal_moves`

Grain:

```text
One row represents one internal employee move event.
```

Primary key:

```text
move_id
```

Foreign keys:

```text
employee_id -> employees.employee_id
from_organization_id -> organizations.organization_id
to_organization_id -> organizations.organization_id
```

Important columns:

| Column | Meaning |
| --- | --- |
| `move_id` | Unique move identifier. |
| `employee_id` | Employee associated with the move. |
| `move_date` | Date the move occurred. |
| `move_type` | Promotion, Lateral Transfer, Organization Transfer, or Role Change. |
| `from_organization_id` | Organization before the move. |
| `to_organization_id` | Organization after the move. |
| `from_job_level` | Job level before the move. |
| `to_job_level` | Job level after the move. |

This table supports questions about:

- Promotions.
- Lateral transfers.
- Organization transfers.
- Role changes.
- Internal mobility trends.
- Later promotions after program completion.

Example question:

```text
Did Leadership Development completion correlate with later promotions?
```

## 5. Business Units And Controlled Values

Business units:

```text
Technology
Operations
Customer Experience
Finance
People
Sales
Marketing
```

Regions:

```text
North America
Europe
Asia Pacific
Latin America
```

Job levels:

```text
L2
L3
L4
L5
L6
L7
```

Job families:

```text
Data
Software Engineering
Product
Program Management
Operations
Finance
HR
Sales
Marketing
```

Review cycles:

```text
2024_H1
2024_H2
2025_H1
2025_H2
2026_H1
2026_H2
```

## 6. Business Metrics

### Active Headcount

Default definition:

```text
Count employees where employment_status = 'Active'.
```

Point-in-time definition:

```text
Count employees where hire_date <= point_in_time
and (termination_date is null or termination_date > point_in_time).
```

Example question:

```text
What percentage of active employees is in each business unit?
```

### Review Completion Rate

Definition:

```text
Completed reviews / non-cancelled expected reviews
```

SQL logic:

```text
review_status = 'Completed'
/
review_status != 'Cancelled'
```

Example question:

```text
What was the 2026 H1 talent review completion rate?
```

### Program Completion Rate

Definition:

```text
Completed employee_programs enrollments / non-withdrawn enrollments
```

SQL logic:

```text
participation_status = 'Completed'
/
participation_status != 'Withdrawn'
```

Example question:

```text
Which development program had the highest completion rate?
```

### Promotion Rate

Definition:

```text
Unique employees with at least one internal_moves row where move_type = 'Promotion'
/
chosen eligible workforce denominator
```

When the question does not specify a denominator, the agent generally uses active employees for the same grouping.

### Internal Mobility Rate

Definition:

```text
Unique employees with at least one qualifying internal_moves row
/
chosen active workforce denominator
```

Qualifying moves can include promotions, lateral transfers, organization transfers, and role changes depending on the question.

### High Performance

Definition:

```text
performance_rating >= 4
```

## 7. Question Families

Good-fit questions are aggregate workforce analytics questions.

### Headcount

```text
How many active employees are in each business unit?
Which organization has the highest active headcount?
What percentage of active employees is in each business unit?
```

### Talent Reviews

```text
What was the 2026 H1 talent review completion rate?
Which business unit had the best 2026 H1 reviews?
Which business unit had the highest average performance rating in 2026 H1?
```

### Development Programs

```text
Which development program had the highest completion rate?
Which program type had the most completed enrollments?
What was the completion rate by program type?
```

### Mobility And Promotions

```text
How many employees were promoted in Q2 2026?
What was the annual internal mobility trend from 2024 through 2026?
Did Leadership Development completion correlate with later promotions?
```

### Follow-Up Questions

After a full first question, the assistant supports lightweight current-session follow-ups.

Examples:

```text
What about Technology?
Show percentages instead.
Compare that with Sales.
```

## 8. Questions That Are Out Of Scope

The dataset is not designed for:

- Individual private employee lookup.
- Salaries or compensation.
- Protected attributes or demographic analysis.
- Real employee records.
- Weather, market prices, current events, or external facts.
- Legal, HR policy, or employment advice.
- Production HR decision-making.

The agent should answer aggregate analytics questions grounded in the six synthetic tables.

## 9. How The Agent Uses This Data

The agent does not blindly expose the full database schema to the model every time. It uses metadata-driven schema retrieval.

RAG pipeline:

```text
metadata/tables/*.yaml
  -> serialized table documents
  -> embedding/vector search
  -> lexical reranking
  -> top schema context
  -> SQL generation
```

Each table document includes:

- Description.
- Grain.
- Primary key.
- Foreign keys.
- Columns.
- Sample rows.

At runtime, the retrieved table context is passed to the SQL generation step. The resulting SQL is then validated before execution.

This means the data guide, metadata YAML, RAG context, and SQL validation layer all work together:

```text
Data guide -> human understanding
metadata YAML -> machine-readable schema context
RAG retrieval -> relevant table context
SQL validator -> execution safety
DuckDB -> grounded result
Summary node -> natural-language answer
```

## 10. Data Design Notes

The synthetic data intentionally includes patterns that are useful for demos and evaluation:

- Workforce headcount varies across business units.
- Talent review completion can be measured by review cycle.
- Development program completion can be compared across programs.
- Leadership Development completion has a synthetic correlation with later promotions.
- Internal mobility events support promotion and transfer questions.

Important caution:

```text
The Leadership Development promotion relationship is synthetic correlation, not causal evidence.
```

## 11. Reviewer Path

For a quick data-focused review:

1. Read the table overview in this guide.
2. Open `metadata/tables/*.yaml`.
3. Ask the app: `How many active employees are in each business unit?`
4. Open `Show workflow details`.
5. Check which tables were retrieved.
6. Inspect the generated SQL.
7. Compare the SQL joins against the relationship model in this guide.

That path shows how the dataset, schema metadata, RAG retrieval, SQL generation, and final answer connect end to end.

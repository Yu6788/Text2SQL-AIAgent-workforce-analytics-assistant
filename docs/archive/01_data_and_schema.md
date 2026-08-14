# Atlas Workforce Text-to-SQL — Data and Schema Specification

## 1. Objective

Create a deterministic, realistic synthetic workforce dataset that supports:

- headcount analytics
- performance/talent reviews
- development program analytics
- promotions
- internal mobility
- historical trend analysis
- multi-table joins

The generated data must be useful for Text-to-SQL evaluation. It should contain intentional business patterns rather than purely independent random noise.

Use a fixed seed:

```python
RANDOM_SEED = 42
```

---

## 2. Time Horizon

Synthetic business history should cover:

```text
2024-01-01 through 2026-12-31
```

This supports year-over-year, half-year, quarterly, and historical trend questions.

---

## 3. Table Overview

V1 contains:

| Table | Approximate Rows | Grain |
|---|---:|---|
| `organizations` | 50 | one organization |
| `employees` | 5,000 | one employee |
| `talent_reviews` | 15,000 | one employee review per review cycle |
| `development_programs` | 40 | one development program |
| `employee_programs` | 8,000 | one employee-program enrollment |
| `internal_moves` | 3,000 | one internal move event |

Exact row counts may vary slightly if required for integrity or realistic temporal generation.

---

## 4. Relationship Model

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

Relationships:

```text
employees.organization_id
    -> organizations.organization_id

employees.manager_id
    -> employees.employee_id

talent_reviews.employee_id
    -> employees.employee_id

employee_programs.employee_id
    -> employees.employee_id

employee_programs.program_id
    -> development_programs.program_id

internal_moves.employee_id
    -> employees.employee_id

internal_moves.from_organization_id
    -> organizations.organization_id

internal_moves.to_organization_id
    -> organizations.organization_id
```

---

## 5. `organizations`

### Purpose

Represents organizational units.

### Schema

```text
organization_id      VARCHAR PRIMARY KEY
organization_name    VARCHAR
business_unit        VARCHAR
region               VARCHAR
org_leader_id        VARCHAR NULL
created_date         DATE
organization_status  VARCHAR
```

### Controlled Business Units

- Technology
- Operations
- Customer Experience
- Finance
- People
- Sales
- Marketing

### Controlled Regions

- North America
- Europe
- Asia Pacific
- Latin America

### Status Values

- Active
- Inactive

### Generation Notes

`org_leader_id` may be null during initial generation and backfilled after employees are created.

---

## 6. `employees`

### Purpose

Represents employees without unnecessary PII.

### Schema

```text
employee_id         VARCHAR PRIMARY KEY
hire_date           DATE
termination_date    DATE NULL
employment_status   VARCHAR
job_level           VARCHAR
job_family          VARCHAR
location            VARCHAR
manager_id          VARCHAR NULL
organization_id     VARCHAR
```

### Job Levels

```text
L2
L3
L4
L5
L6
L7
```

### Job Families

- Data
- Software Engineering
- Product
- Program Management
- Operations
- Finance
- HR
- Sales
- Marketing

### Employment Status

- Active
- Terminated
- Leave

### PII Policy

Do not generate:

- names
- email addresses
- phone numbers
- home addresses
- race
- gender
- protected characteristics

These fields are unnecessary for the analytical scenario.

---

## 7. `talent_reviews`

### Purpose

Stores employee talent and performance review records.

### Schema

```text
review_id                 VARCHAR PRIMARY KEY
employee_id               VARCHAR
review_cycle              VARCHAR
review_date               DATE
performance_rating        INTEGER
potential_rating          INTEGER
promotion_recommended     BOOLEAN
review_status             VARCHAR
```

### Review Cycles

- `2024_H1`
- `2024_H2`
- `2025_H1`
- `2025_H2`
- `2026_H1`
- `2026_H2`

### Rating Scale

```text
1 through 5
```

### Review Status

- Completed
- Pending
- Cancelled

### Distribution Rules

Performance ratings should not be uniform.

Recommended tendency:

```text
1 -> rare
2 -> uncommon
3 -> most common
4 -> common
5 -> uncommon
```

Promotion recommendations should become more likely as performance and potential ratings rise.

---

## 8. `development_programs`

### Purpose

Stores workforce and talent development programs.

### Schema

```text
program_id          VARCHAR PRIMARY KEY
program_name        VARCHAR
program_type        VARCHAR
start_date          DATE
end_date            DATE
target_job_level    VARCHAR
program_status      VARCHAR
```

### Program Types

- Leadership Development
- Technical Upskilling
- Mentorship
- Career Development
- Manager Training

### Status

- Planned
- Active
- Completed
- Cancelled

---

## 9. `employee_programs`

### Purpose

Many-to-many bridge between employees and development programs.

### Schema

```text
employee_program_id    VARCHAR PRIMARY KEY
employee_id            VARCHAR
program_id             VARCHAR
enrollment_date        DATE
completion_date        DATE NULL
participation_status   VARCHAR
completion_score       DOUBLE NULL
```

### Participation Status

- Enrolled
- In Progress
- Completed
- Withdrawn

### Temporal Rule

If `completion_date` exists:

```text
completion_date >= enrollment_date
```

---

## 10. `internal_moves`

### Purpose

Stores employee internal mobility events.

### Schema

```text
move_id                 VARCHAR PRIMARY KEY
employee_id             VARCHAR
move_date               DATE
move_type               VARCHAR
from_organization_id    VARCHAR
to_organization_id      VARCHAR
from_job_level           VARCHAR
to_job_level             VARCHAR
```

### Move Types

- Promotion
- Lateral Transfer
- Organization Transfer
- Role Change

### Rules

Promotion:

```text
to_job_level > from_job_level
```

Lateral Transfer:

```text
to_job_level == from_job_level
```

Organization Transfer:

```text
from_organization_id != to_organization_id
```

Role Change:

- may keep the same level
- may remain in the same organization or move organizations

---

## 11. Required Synthetic Business Patterns

The generator must intentionally encode these patterns.

### 11.1 Workforce Growth

Approximate active headcount:

```text
2024 -> ~4,200
2025 -> ~4,600
2026 -> ~5,000
```

Exact values may vary slightly.

### 11.2 Promotion Differences by Business Unit

Create observable synthetic differences.

Example tendency:

```text
Technology            ~14%
Operations             ~9%
Customer Experience    ~7%
```

Other units may fall approximately between 7% and 13%.

These are synthetic patterns only.

### 11.3 Development Program Correlation

Employees who complete a Leadership Development program should have a higher later promotion rate than comparable employees without such completion.

Example synthetic tendency:

```text
Leadership program completers -> ~17% later promotion
Others                        -> ~9% later promotion
```

This must be described as **correlation in synthetic data**, not causation.

### 11.4 Review Completion Improvement

Create an improving historical completion trend.

Example:

```text
2024_H1 -> ~82%
2025_H1 -> ~89%
2026_H1 -> ~94%
```

Later cycles may vary while preserving the overall improvement trend.

### 11.5 Performance Distribution

Most ratings should be 3 or 4.

Promotion recommendations should be more common when:

- `performance_rating >= 4`
- `potential_rating >= 4`

### 11.6 Internal Mobility

Promotions generally increase one level.

Examples:

```text
L3 -> L4
L4 -> L5
L5 -> L6
```

Avoid impossible upward moves beyond the defined top level.

---

## 12. Business Definitions

Create:

```text
metadata/business_context.yaml
```

At minimum define:

### Active Headcount

Default current definition:

```text
COUNT employees
WHERE employment_status = 'Active'
```

For historical point-in-time questions:

```text
hire_date <= point_in_time
AND (
    termination_date IS NULL
    OR termination_date > point_in_time
)
```

### Promotion Rate

V1 simplified definition:

```text
unique employees with move_type = 'Promotion'
/
defined eligible workforce denominator
```

The denominator must be documented consistently.

### Review Completion Rate

```text
Completed reviews
/
all non-cancelled expected reviews
```

### Program Completion Rate

```text
Completed enrollments
/
all non-withdrawn enrollments
```

### Internal Mobility Rate

```text
unique employees with >= 1 qualifying internal move
/
defined active workforce denominator
```

### High Performance

```text
performance_rating >= 4
```

---

## 13. Metadata as RAG Documents

Create:

```text
metadata/tables/
    organizations.yaml
    employees.yaml
    talent_reviews.yaml
    development_programs.yaml
    employee_programs.yaml
    internal_moves.yaml
```

One YAML file corresponds to one RAG document.

Required fields:

```yaml
table_name:
description:
grain:
primary_key:
foreign_keys:
columns:
sample_rows:
```

Each column entry should contain:

```yaml
- name:
  type:
  description:
```

Add controlled/common values when useful.

---

## 14. Example Metadata Shape

```yaml
table_name: talent_reviews

description: >
  Contains employee talent and performance review records.

grain: >
  One row represents one employee review in one review cycle.

primary_key:
  - review_id

foreign_keys:
  employee_id:
    references: employees.employee_id

columns:
  - name: review_id
    type: VARCHAR
    description: Unique identifier for the review.

  - name: employee_id
    type: VARCHAR
    description: Employee receiving the review.

  - name: review_cycle
    type: VARCHAR
    description: Review period such as 2026_H1.

sample_rows:
  - review_id: R10001
    employee_id: E10001
    review_cycle: 2026_H1
    review_date: 2026-06-15
    performance_rating: 4
    potential_rating: 4
    promotion_recommended: true
    review_status: Completed
```

---

## 15. Metadata Document Size

Target each serialized retrieval document to approximately:

```text
<= 450 tokens
```

Priority order:

1. table name
2. business description
3. grain
4. columns and descriptions
5. PK/FK relationships
6. useful controlled values
7. one or two sample rows

Do not include long prose or excessive sample rows.

Business metric definitions remain global SQL-generation context and are not duplicated into every table chunk.

---

## 16. Data Generation Workflow

Recommended:

```text
scripts/generate_data.py
        |
        v
data/generated/*.csv or DataFrames
        |
        v
scripts/validate_data.py
        |
        v
scripts/build_database.py
        |
        v
data/atlas_workforce.duckdb
```

Generated data should be rebuildable from scratch.

Large generated artifacts may be excluded from Git if scripts regenerate them reliably.

---

## 17. Data Integrity Validation

The generator must verify:

- all primary keys are unique
- all foreign keys are valid
- manager IDs reference valid employees when present
- hire date precedes relevant reviews
- hire date precedes internal moves
- termination date is after hire date
- review dates match their review cycles reasonably
- program completion date is after enrollment date
- promotion moves increase job level
- lateral transfers preserve job level
- organization transfers change organization
- impossible temporal relationships are rejected
- nulls appear only where logically valid

Validation failure should stop the build.

---

## 18. Representative Questions Supported by the Schema

The schema should support:

- active headcount by business unit
- headcount by region
- review completion by cycle
- average performance rating by business unit
- high-performance rate
- promotion recommendation rate
- program completion rate
- promotion count by quarter
- internal mobility trend
- organization transfer flows
- job level with the most promotions
- leadership program completion vs later promotion

---

## 19. Data Foundation Acceptance Criteria

The data layer is complete when:

- all six tables are generated
- generation is deterministic
- business patterns are observable
- integrity checks pass
- DuckDB builds
- metadata YAML files exist
- business definitions exist
- representative hand-written SQL returns sensible results

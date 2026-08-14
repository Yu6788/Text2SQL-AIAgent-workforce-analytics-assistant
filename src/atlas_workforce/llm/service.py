from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from atlas_workforce.llm.contracts import (
    FollowUpResolutionResult,
    GuardrailResult,
    SQLGenerationResult,
    SQLRepairResult,
    SummaryResult,
)


class LLMService(Protocol):
    provider_name: str
    model_name: str

    def guardrail(self, question: str, database_scope: str) -> GuardrailResult:
        ...

    def generate_sql(
        self,
        question: str,
        business_context: str,
        schema_context: str,
    ) -> SQLGenerationResult:
        ...

    def repair_sql(
        self,
        question: str,
        business_context: str,
        schema_context: str,
        previous_sql: str,
        error_message: str,
        retry_history: list[str],
    ) -> SQLRepairResult:
        ...

    def summarize(
        self,
        question: str,
        sql: str,
        columns: list[str],
        rows: list[tuple],
        truncated: bool,
    ) -> SummaryResult:
        ...

    def resolve_follow_up(
        self,
        question: str,
        previous_question: Optional[str],
        previous_sql: Optional[str],
        previous_answer: Optional[str],
    ) -> FollowUpResolutionResult:
        ...


@dataclass
class StubLLMService:
    """Deterministic local adapter for tests and offline workflow smoke runs."""

    provider_name: str = "local_stub"
    model_name: str = "deterministic_sql_rules_v1"

    def resolve_follow_up(
        self,
        question: str,
        previous_question: Optional[str],
        previous_sql: Optional[str],
        previous_answer: Optional[str],
    ) -> FollowUpResolutionResult:
        if not previous_question:
            return FollowUpResolutionResult(
                resolved_question=question,
                is_follow_up=False,
                reason="No previous question is available.",
            )

        lowered = question.lower().strip()
        previous_lowered = previous_question.lower()
        business_units = [
            ("technology", "Technology"),
            ("operations", "Operations"),
            ("customer experience", "Customer Experience"),
            ("finance", "Finance"),
            ("people", "People"),
            ("sales", "Sales"),
            ("marketing", "Marketing"),
        ]

        if "active employees" in previous_lowered and "business unit" in previous_lowered:
            for unit, label in business_units:
                if unit in lowered:
                    return FollowUpResolutionResult(
                        resolved_question=f"How many active employees are in the {label} business unit?",
                        is_follow_up=True,
                        reason="Resolved business-unit filter from the previous headcount question.",
                    )
            if "percentage" in lowered or "percent" in lowered or "share" in lowered:
                return FollowUpResolutionResult(
                    resolved_question="What percentage of active employees is in each business unit?",
                    is_follow_up=True,
                    reason="Resolved percentage follow-up from the previous headcount question.",
                )

        return FollowUpResolutionResult(
            resolved_question=question,
            is_follow_up=False,
            reason="Question is treated as standalone by the local resolver.",
        )

    def guardrail(self, question: str, database_scope: str) -> GuardrailResult:
        lowered = question.lower()
        allowed_terms = {
            "employee",
            "employees",
            "headcount",
            "organization",
            "business unit",
            "review",
            "promotion",
            "program",
            "mobility",
            "performance",
            "talent",
        }
        unrelated_terms = {"weather", "bitcoin", "poem", "recipe", "stock price"}
        if any(term in lowered for term in unrelated_terms):
            return GuardrailResult(allowed=False, reason="Question is outside the workforce analytics database scope.")
        if any(term in lowered for term in allowed_terms):
            return GuardrailResult(allowed=True, reason="Question appears answerable from workforce analytics tables.")
        return GuardrailResult(allowed=False, reason="Question does not clearly reference supported workforce analytics data.")

    def generate_sql(
        self,
        question: str,
        business_context: str,
        schema_context: str,
    ) -> SQLGenerationResult:
        lowered = question.lower()
        if "repair demo unsafe" in lowered:
            return SQLGenerationResult(
                sql="SELECT * FROM salaries",
                tables_used=["salaries"],
            )
        if "repair demo bad column" in lowered:
            return SQLGenerationResult(
                sql="SELECT employee_status, COUNT(*) AS employees FROM employees GROUP BY employee_status",
                tables_used=["employees"],
            )
        if "active" in lowered and "business unit" in lowered and "employee" in lowered:
            for unit in [
                ("technology", "Technology"),
                ("operations", "Operations"),
                ("customer experience", "Customer Experience"),
                ("finance", "Finance"),
                ("people", "People"),
                ("sales", "Sales"),
                ("marketing", "Marketing"),
            ]:
                unit_key, unit_label = unit
                if unit_key in lowered and "each business unit" not in lowered:
                    return SQLGenerationResult(
                        sql=f"""
                        SELECT
                            o.business_unit,
                            COUNT(*) AS active_headcount
                        FROM employees e
                        JOIN organizations o
                            ON e.organization_id = o.organization_id
                        WHERE e.employment_status = 'Active'
                          AND o.business_unit = '{unit_label}'
                        GROUP BY o.business_unit
                        """.strip(),
                        tables_used=["employees", "organizations"],
                    )
            return SQLGenerationResult(
                sql="""
                SELECT
                    o.business_unit,
                    COUNT(*) AS active_headcount
                FROM employees e
                JOIN organizations o
                    ON e.organization_id = o.organization_id
                WHERE e.employment_status = 'Active'
                GROUP BY o.business_unit
                ORDER BY active_headcount DESC
                """.strip(),
                tables_used=["employees", "organizations"],
            )
        if "percentage of active employees" in lowered and "business unit" in lowered:
            return SQLGenerationResult(
                sql="""
                WITH active_by_bu AS (
                    SELECT
                        o.business_unit,
                        COUNT(*) AS active_headcount
                    FROM employees e
                    JOIN organizations o
                        ON e.organization_id = o.organization_id
                    WHERE e.employment_status = 'Active'
                    GROUP BY o.business_unit
                )
                SELECT
                    business_unit,
                    active_headcount,
                    ROUND(100.0 * active_headcount / SUM(active_headcount) OVER (), 1) AS active_headcount_pct
                FROM active_by_bu
                ORDER BY active_headcount_pct DESC
                """.strip(),
                tables_used=["employees", "organizations"],
            )
        if "organization" in lowered and "highest active headcount" in lowered:
            return SQLGenerationResult(
                sql="""
                SELECT
                    o.organization_name,
                    o.business_unit,
                    COUNT(*) AS active_headcount
                FROM employees e
                JOIN organizations o
                    ON e.organization_id = o.organization_id
                WHERE e.employment_status = 'Active'
                  AND o.organization_status = 'Active'
                GROUP BY o.organization_name, o.business_unit
                ORDER BY active_headcount DESC
                LIMIT 1
                """.strip(),
                tables_used=["employees", "organizations"],
            )
        if "2026 h1" in lowered and "review completion" in lowered:
            return SQLGenerationResult(
                sql="""
                SELECT
                    ROUND(
                        100.0 * SUM(CASE WHEN review_status = 'Completed' THEN 1 ELSE 0 END)
                        / NULLIF(SUM(CASE WHEN review_status != 'Cancelled' THEN 1 ELSE 0 END), 0),
                        1
                    ) AS review_completion_rate_pct
                FROM talent_reviews
                WHERE review_cycle = '2026_H1'
                """.strip(),
                tables_used=["talent_reviews"],
            )
        if (
            "business unit" in lowered
            and "2026 h1" in lowered
            and ("best" in lowered or "highest" in lowered)
            and ("review" in lowered or "reviews" in lowered or "performance" in lowered)
        ):
            return SQLGenerationResult(
                sql="""
                SELECT
                    o.business_unit,
                    ROUND(AVG(tr.performance_rating), 2) AS average_performance_rating,
                    COUNT(*) AS completed_reviews
                FROM talent_reviews tr
                JOIN employees e
                    ON tr.employee_id = e.employee_id
                JOIN organizations o
                    ON e.organization_id = o.organization_id
                WHERE tr.review_cycle = '2026_H1'
                  AND tr.review_status = 'Completed'
                GROUP BY o.business_unit
                ORDER BY average_performance_rating DESC, completed_reviews DESC
                LIMIT 1
                """.strip(),
                tables_used=["talent_reviews", "employees", "organizations"],
            )
        if "development program" in lowered and "completion rate" in lowered:
            return SQLGenerationResult(
                sql="""
                SELECT
                    dp.program_name,
                    dp.program_type,
                    ROUND(
                        100.0 * SUM(CASE WHEN ep.participation_status = 'Completed' THEN 1 ELSE 0 END)
                        / NULLIF(SUM(CASE WHEN ep.participation_status != 'Withdrawn' THEN 1 ELSE 0 END), 0),
                        1
                    ) AS completion_rate_pct
                FROM employee_programs ep
                JOIN development_programs dp
                    ON ep.program_id = dp.program_id
                GROUP BY dp.program_name, dp.program_type
                ORDER BY completion_rate_pct DESC
                LIMIT 1
                """.strip(),
                tables_used=["employee_programs", "development_programs"],
            )
        if (
            "leadership development" in lowered
            and "promotion" in lowered
            and ("later" in lowered or "correlation" in lowered or "higher" in lowered)
        ):
            return SQLGenerationResult(
                sql="""
                WITH leadership_completed AS (
                    SELECT
                        ep.employee_id,
                        MIN(ep.completion_date) AS completion_date
                    FROM employee_programs ep
                    JOIN development_programs dp
                        ON ep.program_id = dp.program_id
                    WHERE dp.program_type = 'Leadership Development'
                      AND ep.participation_status = 'Completed'
                      AND ep.completion_date IS NOT NULL
                    GROUP BY ep.employee_id
                ),
                employee_cohorts AS (
                    SELECT
                        e.employee_id,
                        CASE
                            WHEN lc.employee_id IS NOT NULL THEN 'Completed Leadership Development'
                            ELSE 'Did not complete Leadership Development'
                        END AS cohort,
                        lc.completion_date
                    FROM employees e
                    LEFT JOIN leadership_completed lc
                        ON e.employee_id = lc.employee_id
                    WHERE e.employment_status = 'Active'
                ),
                promotion_flags AS (
                    SELECT
                        ec.cohort,
                        ec.employee_id,
                        MAX(
                            CASE
                                WHEN im.move_type = 'Promotion'
                                 AND (
                                     ec.completion_date IS NULL
                                     OR im.move_date > ec.completion_date
                                 )
                                THEN 1
                                ELSE 0
                            END
                        ) AS had_later_promotion
                    FROM employee_cohorts ec
                    LEFT JOIN internal_moves im
                        ON ec.employee_id = im.employee_id
                    GROUP BY ec.cohort, ec.employee_id
                )
                SELECT
                    cohort,
                    COUNT(*) AS employees,
                    SUM(had_later_promotion) AS promoted_employees,
                    ROUND(100.0 * SUM(had_later_promotion) / NULLIF(COUNT(*), 0), 1) AS promotion_rate_pct
                FROM promotion_flags
                GROUP BY cohort
                ORDER BY promotion_rate_pct DESC
                """.strip(),
                tables_used=["employees", "employee_programs", "development_programs", "internal_moves"],
            )
        raise ValueError("StubLLMService does not have a deterministic SQL rule for this question.")

    def repair_sql(
        self,
        question: str,
        business_context: str,
        schema_context: str,
        previous_sql: str,
        error_message: str,
        retry_history: list[str],
    ) -> SQLRepairResult:
        lowered = question.lower()
        if "repair demo unsafe" in lowered:
            return SQLRepairResult(
                sql="SELECT COUNT(*) AS active_employees FROM employees WHERE employment_status = 'Active'"
            )
        if "repair demo bad column" in lowered:
            return SQLRepairResult(
                sql="SELECT employment_status, COUNT(*) AS employees FROM employees GROUP BY employment_status ORDER BY employment_status"
            )
        generated = self.generate_sql(question, business_context, schema_context)
        return SQLRepairResult(sql=generated.sql)

    def summarize(
        self,
        question: str,
        sql: str,
        columns: list[str],
        rows: list[tuple],
        truncated: bool,
    ) -> SummaryResult:
        if not rows:
            return SummaryResult(answer="The query returned zero rows.")

        lowered_columns = [column.lower() for column in columns]
        lowered_question = question.lower()
        suffix = " The result was truncated." if truncated else ""

        if columns == ["business_unit", "active_headcount"]:
            sorted_rows = sorted(rows, key=lambda row: row[1], reverse=True)
            leader = sorted_rows[0]
            if len(sorted_rows) >= 3:
                second = sorted_rows[1]
                third = sorted_rows[2]
                return SummaryResult(
                    answer=(
                        f"{leader[0]} has the highest active headcount with {leader[1]:,} employees, "
                        f"followed by {second[0]} with {second[1]:,} and {third[0]} with {third[1]:,}. "
                        f"The result covers {len(rows)} business units.{suffix}"
                    )
                )
            return SummaryResult(answer=f"{leader[0]} has {leader[1]:,} active employees.{suffix}")

        if {"organization_name", "business_unit", "active_headcount"}.issubset(set(lowered_columns)):
            row = rows[0]
            organization = row[lowered_columns.index("organization_name")]
            business_unit = row[lowered_columns.index("business_unit")]
            headcount = row[lowered_columns.index("active_headcount")]
            return SummaryResult(
                answer=(
                    f"{organization} in {business_unit} has the highest active headcount "
                    f"with {int(headcount):,} employees.{suffix}"
                )
            )

        if "review_completion_rate_pct" in lowered_columns:
            value = rows[0][lowered_columns.index("review_completion_rate_pct")]
            return SummaryResult(answer=f"The talent review completion rate was {float(value):.1f}%.{suffix}")

        if "review_completion_rate" in lowered_columns:
            value = rows[0][lowered_columns.index("review_completion_rate")]
            return SummaryResult(answer=f"The talent review completion rate was {float(value) * 100:.1f}%.{suffix}")

        if "completion_rate_pct" in lowered_columns and "program_name" in lowered_columns:
            row = rows[0]
            program = row[lowered_columns.index("program_name")]
            rate = row[lowered_columns.index("completion_rate_pct")]
            return SummaryResult(
                answer=f"{program} had the highest program completion rate at {float(rate):.1f}%.{suffix}"
            )

        if {"business_unit", "average_performance_rating", "completed_reviews"}.issubset(set(lowered_columns)):
            row = rows[0]
            business_unit = row[lowered_columns.index("business_unit")]
            rating = row[lowered_columns.index("average_performance_rating")]
            reviews = row[lowered_columns.index("completed_reviews")]
            return SummaryResult(
                answer=(
                    f"{business_unit} had the best 2026 H1 reviews, with an average performance "
                    f"rating of {float(rating):.2f} across {int(reviews):,} completed reviews.{suffix}"
                )
            )

        if {"cohort", "employees", "promoted_employees", "promotion_rate_pct"}.issubset(set(lowered_columns)):
            cohort_idx = lowered_columns.index("cohort")
            employees_idx = lowered_columns.index("employees")
            promoted_idx = lowered_columns.index("promoted_employees")
            rate_idx = lowered_columns.index("promotion_rate_pct")
            sorted_rows = sorted(rows, key=lambda row: float(row[rate_idx]), reverse=True)
            fragments = [
                (
                    f"{row[cohort_idx]}: {float(row[rate_idx]):.1f}% "
                    f"({int(row[promoted_idx]):,} of {int(row[employees_idx]):,} employees)"
                )
                for row in sorted_rows
            ]
            if len(sorted_rows) >= 2:
                return SummaryResult(
                    answer=(
                        "Promotion rates by cohort are "
                        + "; ".join(fragments)
                        + ". This is a synthetic correlation, not evidence of causation."
                        + suffix
                    )
                )
            return SummaryResult(answer="Promotion rate by cohort is " + "; ".join(fragments) + "." + suffix)

        if columns == ["employment_status", "employees"]:
            fragments = [f"{status}: {count:,}" for status, count in rows]
            return SummaryResult(answer=f"Employee counts by status are {', '.join(fragments)}.{suffix}")

        if len(rows) == 1 and len(columns) == 1:
            value = rows[0][0]
            if isinstance(value, float) and 0 <= value <= 1 and "rate" in lowered_columns[0]:
                return SummaryResult(answer=f"{columns[0].replace('_', ' ')} was {value * 100:.1f}%.{suffix}")
            if isinstance(value, int):
                return SummaryResult(answer=f"{columns[0].replace('_', ' ').capitalize()} was {value:,}.{suffix}")
            return SummaryResult(answer=f"{columns[0].replace('_', ' ').capitalize()} was {value}.{suffix}")

        preview = rows[:5]
        formatted_rows = [
            ", ".join(f"{column}: {value}" for column, value in zip(columns, row))
            for row in preview
        ]
        if "highest" in lowered_question and preview:
            return SummaryResult(answer=f"The top result is {formatted_rows[0]}.{suffix}")
        return SummaryResult(answer="; ".join(formatted_rows) + "." + suffix)

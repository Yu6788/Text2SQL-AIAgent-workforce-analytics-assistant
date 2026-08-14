from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class GuardrailResult(BaseModel):
    allowed: bool
    reason: str


class SQLGenerationResult(BaseModel):
    sql: str
    tables_used: list[str] = Field(default_factory=list)


class SQLRepairResult(BaseModel):
    sql: str


class SummaryResult(BaseModel):
    answer: str

    @field_validator("answer", mode="before")
    @classmethod
    def coerce_answer_to_string(cls, value: object) -> str:
        return str(value)


class FollowUpResolutionResult(BaseModel):
    resolved_question: str
    is_follow_up: bool
    reason: str

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional, Type, TypeVar

import requests
from pydantic import BaseModel, ValidationError

from atlas_workforce.llm.contracts import (
    FollowUpResolutionResult,
    GuardrailResult,
    SQLGenerationResult,
    SQLRepairResult,
    SummaryResult,
)
from atlas_workforce.llm.service import LLMService


T = TypeVar("T", bound=BaseModel)


class LLMProviderError(RuntimeError):
    pass


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        loaded = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        if start >= 0:
            try:
                loaded, _ = json.JSONDecoder().raw_decode(cleaned[start:])
            except json.JSONDecodeError:
                loaded = None
            if isinstance(loaded, dict):
                return loaded
        match = re.search(r"\{.*?\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        loaded = json.loads(match.group(0))
    if not isinstance(loaded, dict):
        raise ValueError("Expected a JSON object from LLM response")
    return loaded


@dataclass
class OpenAICompatibleLLMService:
    api_key: str
    model_name: str
    base_url: str = "https://api.openai.com/v1"
    provider_name: str = "openai_compatible"
    request_timeout_seconds: int = 30
    max_structured_retries: int = 1
    session: requests.Session | None = None

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        if self.session is None:
            self.session = requests.Session()

    def guardrail(self, question: str, database_scope: str) -> GuardrailResult:
        messages = [
            {
                "role": "system",
                "content": (
                    "You classify whether a question is answerable from the provided "
                    "database scope. Return only JSON with keys: allowed, reason."
                ),
            },
            {
                "role": "user",
                "content": f"Database scope:\n{database_scope}\n\nQuestion:\n{question}",
            },
        ]
        return self._generate_structured(messages, GuardrailResult)

    def resolve_follow_up(
        self,
        question: str,
        previous_question: Optional[str],
        previous_sql: Optional[str],
        previous_answer: Optional[str],
    ) -> FollowUpResolutionResult:
        messages = [
            {
                "role": "system",
                "content": (
                    "Resolve a possible follow-up analytics question into a standalone "
                    "workforce analytics question. Return only JSON with keys: "
                    "resolved_question, is_follow_up, reason. If the question is already "
                    "standalone, return it unchanged and set is_follow_up to false."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Previous question:\n{previous_question or ''}\n\n"
                    f"Previous SQL:\n{previous_sql or ''}\n\n"
                    f"Previous answer:\n{previous_answer or ''}\n\n"
                    f"New user question:\n{question}"
                ),
            },
        ]
        return self._generate_structured(messages, FollowUpResolutionResult)

    def generate_sql(
        self,
        question: str,
        business_context: str,
        schema_context: str,
    ) -> SQLGenerationResult:
        messages = [
            {
                "role": "system",
                "content": (
                    "Generate one safe DuckDB SELECT query. Return only JSON with keys: "
                    "sql, tables_used. tables_used must be a list of table names. Do not "
                    "include explanations."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Business definitions:\n{business_context}\n\n"
                    f"Available schema context:\n{schema_context}\n\n"
                    f"User question:\n{question}"
                ),
            },
        ]
        return self._generate_structured(messages, SQLGenerationResult)

    def repair_sql(
        self,
        question: str,
        business_context: str,
        schema_context: str,
        previous_sql: str,
        error_message: str,
        retry_history: list[str],
    ) -> SQLRepairResult:
        messages = [
            {
                "role": "system",
                "content": (
                    "Repair the DuckDB SQL query. Return only JSON with key: sql. "
                    "The SQL must be one read-only SELECT or WITH ... SELECT query."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\n"
                    f"Business definitions:\n{business_context}\n\n"
                    f"Schema context:\n{schema_context}\n\n"
                    f"Previous SQL:\n{previous_sql}\n\n"
                    f"Current error:\n{error_message}\n\n"
                    f"Retry history:\n{retry_history}"
                ),
            },
        ]
        return self._generate_structured(messages, SQLRepairResult)

    def summarize(
        self,
        question: str,
        sql: str,
        columns: list[str],
        rows: list[tuple],
        truncated: bool,
    ) -> SummaryResult:
        messages = [
            {
                "role": "system",
                "content": (
                    "Summarize the database result concisely. Return only JSON with key: answer. "
                    "The answer value must be a natural-language string, not a bare number, "
                    "array, or object."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\n"
                    f"SQL:\n{sql}\n\n"
                    f"Columns:\n{columns}\n\n"
                    f"Rows:\n{rows}\n\n"
                    f"Truncated:\n{truncated}"
                ),
            },
        ]
        return self._generate_structured(messages, SummaryResult)

    def _generate_structured(self, messages: list[dict[str, str]], output_schema: Type[T]) -> T:
        last_error: Exception | None = None
        for attempt in range(self.max_structured_retries + 1):
            try:
                content = self._chat_completion(messages)
                data = extract_json_object(content)
                return output_schema.model_validate(data)
            except (json.JSONDecodeError, ValueError, ValidationError, LLMProviderError) as exc:
                last_error = exc
                if attempt >= self.max_structured_retries:
                    break
                messages = messages + [
                    {
                        "role": "user",
                        "content": (
                            "Your previous response did not match the required JSON schema. "
                            "Return strict JSON only, with no markdown or explanation."
                        ),
                    }
                ]
        raise LLMProviderError(f"Structured output failed: {last_error}")

    def _chat_completion(self, messages: list[dict[str, str]]) -> str:
        assert self.session is not None
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        response = self.session.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.request_timeout_seconds,
        )
        if response.status_code >= 400:
            raise LLMProviderError(f"Provider HTTP {response.status_code}: {response.text[:500]}")
        body = response.json()
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(f"Unexpected provider response shape: {body}") from exc

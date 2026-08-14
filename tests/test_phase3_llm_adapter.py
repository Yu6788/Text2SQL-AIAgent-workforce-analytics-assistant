from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from atlas_workforce.llm.factory import create_llm_service  # noqa: E402
from atlas_workforce.llm.openai_compatible import (  # noqa: E402
    LLMProviderError,
    OpenAICompatibleLLMService,
    extract_json_object,
)
from atlas_workforce.llm.service import StubLLMService  # noqa: E402


class FakeResponse:
    def __init__(self, status_code: int, body: dict, text: str = "") -> None:
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self) -> dict:
        return self._body


class FakeSession:
    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.requests = []

    def post(self, url: str, headers: dict, json: dict, timeout: int) -> FakeResponse:
        self.requests.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        content = self.contents.pop(0)
        return FakeResponse(
            200,
            {"choices": [{"message": {"content": content}}]},
        )


def test_extract_json_object_handles_markdown_fence() -> None:
    assert extract_json_object('```json\n{"allowed": true, "reason": "ok"}\n```') == {
        "allowed": True,
        "reason": "ok",
    }


def test_extract_json_object_uses_first_complete_object() -> None:
    assert extract_json_object('{"answer": "ok"}\n{"extra": true}') == {"answer": "ok"}


def test_openai_compatible_guardrail_parses_structured_response() -> None:
    session = FakeSession(['{"allowed": true, "reason": "workforce question"}'])
    service = OpenAICompatibleLLMService(
        api_key="test-key",
        model_name="test-model",
        base_url="https://example.test/v1",
        session=session,
    )

    result = service.guardrail("How many employees are active?", "employees table")

    assert result.allowed
    assert result.reason == "workforce question"
    assert session.requests[0]["url"] == "https://example.test/v1/chat/completions"
    assert session.requests[0]["json"]["response_format"] == {"type": "json_object"}


def test_openai_compatible_retries_invalid_structured_output() -> None:
    session = FakeSession(["not json", '{"sql": "SELECT * FROM employees", "tables_used": ["employees"]}'])
    service = OpenAICompatibleLLMService(
        api_key="test-key",
        model_name="test-model",
        base_url="https://example.test/v1",
        max_structured_retries=1,
        session=session,
    )

    result = service.generate_sql("How many employees?", "business", "schema")

    assert result.sql == "SELECT * FROM employees"
    assert len(session.requests) == 2


def test_openai_compatible_raises_after_structured_output_failures() -> None:
    session = FakeSession(["not json", "still not json"])
    service = OpenAICompatibleLLMService(
        api_key="test-key",
        model_name="test-model",
        base_url="https://example.test/v1",
        max_structured_retries=1,
        session=session,
    )

    with pytest.raises(LLMProviderError):
        service.summarize("q", "sql", ["col"], [(1,)], False)


def test_llm_factory_uses_stub_without_key(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("LLM_PROVIDER=stub\n", encoding="utf-8")

    service = create_llm_service(
        provider="openai_compatible",
        model="unused",
        base_url="https://example.test/v1",
        request_timeout_seconds=30,
        structured_output_retries=1,
        env_path=str(env_path),
    )

    assert isinstance(service, StubLLMService)


def test_llm_factory_requires_key_for_openai_compatible(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("LLM_PROVIDER=openai_compatible\nLLM_MODEL=test\nLLM_BASE_URL=https://example.test/v1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="LLM_API_KEY"):
        create_llm_service(
            provider="stub",
            model="unused",
            base_url=None,
            request_timeout_seconds=30,
            structured_output_retries=1,
            env_path=str(env_path),
        )

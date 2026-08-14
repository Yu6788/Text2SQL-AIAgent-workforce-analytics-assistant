from __future__ import annotations

from atlas_workforce.config.settings import get_env_value, load_env_file
from atlas_workforce.llm.openai_compatible import OpenAICompatibleLLMService
from atlas_workforce.llm.service import LLMService, StubLLMService


def create_llm_service(
    provider: str,
    model: str,
    base_url: str | None,
    request_timeout_seconds: int,
    structured_output_retries: int,
    env_path: str = ".env",
) -> LLMService:
    env_file = load_env_file(env_path)
    env_provider = get_env_value("LLM_PROVIDER", env_file)
    env_model = get_env_value("LLM_MODEL", env_file)
    env_base_url = get_env_value("LLM_BASE_URL", env_file)
    api_key = get_env_value("LLM_API_KEY", env_file)

    selected_provider = env_provider or provider
    selected_model = env_model or model
    selected_base_url = env_base_url or base_url

    if selected_provider in {"stub", "local_stub"}:
        return StubLLMService()

    if selected_provider in {"openai_compatible", "openai", "openrouter"}:
        if not api_key:
            raise ValueError("LLM_API_KEY is required for openai-compatible providers.")
        if selected_provider == "openrouter" and not selected_base_url:
            selected_base_url = "https://openrouter.ai/api/v1"
        if selected_provider == "openai" and not selected_base_url:
            selected_base_url = "https://api.openai.com/v1"
        if not selected_base_url:
            raise ValueError("LLM_BASE_URL is required for openai_compatible provider.")
        return OpenAICompatibleLLMService(
            api_key=api_key,
            model_name=selected_model,
            base_url=selected_base_url,
            provider_name=selected_provider,
            request_timeout_seconds=request_timeout_seconds,
            max_structured_retries=structured_output_retries,
        )

    raise ValueError(f"Unsupported LLM provider: {selected_provider}")

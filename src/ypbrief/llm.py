from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .config import Settings
from .provider_defaults import BUILTIN_PROVIDER_DEFAULTS, normalize_provider


class ConfigError(ValueError):
    pass


class SummaryProvider(Protocol):
    name: str
    model: str

    def summarize(self, prompt: str, transcript: str) -> str:
        ...


@dataclass(frozen=True)
class OpenAICompatibleProvider:
    name: str
    api_key: str
    base_url: str
    model: str

    def summarize(self, prompt: str, transcript: str) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install ypbrief[llm] to use OpenAI-compatible providers") from exc

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": transcript},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content or ""


@dataclass(frozen=True)
class GeminiProvider:
    name: str
    api_key: str
    model: str

    def summarize(self, prompt: str, transcript: str) -> str:
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("Install ypbrief[llm] to use Gemini") from exc

        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.model,
            contents=f"{prompt}\n\n{transcript}",
        )
        return response.text or ""


@dataclass(frozen=True)
class ClaudeProvider:
    name: str
    api_key: str
    model: str

    def summarize(self, prompt: str, transcript: str) -> str:
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError("Install ypbrief[llm] to use Claude") from exc

        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=prompt,
            messages=[{"role": "user", "content": transcript}],
        )
        return "".join(getattr(block, "text", "") for block in response.content)


def create_provider(settings: Settings) -> SummaryProvider:
    provider = normalize_provider(settings.llm_provider)
    if provider == "openai":
        return _openai_compatible(
            name="openai",
            api_key=settings.openai_api_key,
            env_name="OPENAI_API_KEY",
            base_url=settings.openai_base_url or _default_base_url("openai"),
            model=settings.openai_model or settings.llm_model,
        )
    if provider == "siliconflow":
        return _openai_compatible(
            name="siliconflow",
            api_key=settings.siliconflow_api_key,
            env_name="SILICONFLOW_API_KEY",
            base_url=settings.siliconflow_base_url or _default_base_url("siliconflow"),
            model=settings.siliconflow_model or settings.llm_model,
        )
    if provider == "openrouter":
        return _openai_compatible(
            name="openrouter",
            api_key=settings.openrouter_api_key,
            env_name="OPENROUTER_API_KEY",
            base_url=settings.openrouter_base_url or _default_base_url("openrouter"),
            model=settings.openrouter_model or settings.llm_model,
        )
    if provider == "xai":
        return _openai_compatible(
            name="xai",
            api_key=settings.xai_api_key,
            env_name="XAI_API_KEY",
            base_url=settings.xai_base_url or _default_base_url("xai"),
            model=settings.xai_model or settings.llm_model,
        )
    if provider == "deepseek":
        return _openai_compatible(
            name="deepseek",
            api_key=settings.deepseek_api_key,
            env_name="DEEPSEEK_API_KEY",
            base_url=settings.deepseek_base_url or _default_base_url("deepseek"),
            model=settings.deepseek_model or settings.llm_model,
        )
    if provider == "custom_openai":
        if not settings.custom_openai_base_url:
            raise ConfigError("CUSTOM_OPENAI_BASE_URL is required for custom_openai")
        return _openai_compatible(
            name="custom_openai",
            api_key=settings.custom_openai_api_key,
            env_name="CUSTOM_OPENAI_API_KEY",
            base_url=settings.custom_openai_base_url,
            model=settings.custom_openai_model or settings.llm_model,
        )
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise ConfigError("GEMINI_API_KEY is required for gemini")
        return GeminiProvider(
            name="gemini",
            api_key=settings.gemini_api_key,
            model=_required_model("gemini", settings.gemini_model or settings.llm_model),
        )
    if provider == "claude":
        if not settings.anthropic_api_key:
            raise ConfigError("ANTHROPIC_API_KEY is required for claude")
        return ClaudeProvider(
            name="claude",
            api_key=settings.anthropic_api_key,
            model=_required_model("claude", settings.claude_model or settings.llm_model),
        )
    raise ConfigError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")


def _openai_compatible(
    name: str,
    api_key: str,
    env_name: str,
    base_url: str,
    model: str,
) -> OpenAICompatibleProvider:
    if not api_key:
        raise ConfigError(f"{env_name} is required for {name}")
    if not model:
        raise ConfigError(f"Model is required for {name}")
    return OpenAICompatibleProvider(name=name, api_key=api_key, base_url=base_url, model=model)


def _default_base_url(provider: str) -> str:
    return BUILTIN_PROVIDER_DEFAULTS[normalize_provider(provider)]["base_url"]


def _required_model(provider: str, model: str) -> str:
    if not model:
        raise ConfigError(f"Model is required for {provider}")
    return model

"""
LLM abstraction layer.
Supports: openai, anthropic, ollama (via OpenAI-compatible API).
"""
from __future__ import annotations
import json
import logging
from typing import Any, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Thin wrapper around LLM providers.
    All prompts pass through this single interface to ensure
    consistent token counting and provider switching.
    """

    def __init__(self):
        self.provider = settings.llm_provider.lower()
        self.model = settings.llm_model
        self._client = self._build_client()

    def _build_client(self) -> Any:
        if self.provider == "openai":
            from openai import OpenAI
            return OpenAI(api_key=settings.llm_api_key)
        elif self.provider == "anthropic":
            from anthropic import Anthropic
            return Anthropic(api_key=settings.llm_api_key)
        elif self.provider == "ollama":
            from openai import OpenAI
            return OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama",
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider!r}")

    @staticmethod
    def _strip_thinking_tags(text: str) -> str:
        """
        Remove <think>...</think> reasoning blocks that deepseek-r1 and
        other reasoning models emit before the actual answer.
        We strip them so JSON parsing is not broken.
        """
        import re
        # Remove <think>...</think> blocks (including multiline)
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        return cleaned.strip()

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> tuple[str, dict]:
        """
        Call the LLM and return (response_text, usage_dict).
        usage_dict contains prompt_tokens, completion_tokens, total_tokens.
        """
        try:
            if self.provider in ("openai", "ollama"):
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "text"},
                )
                text = response.choices[0].message.content or ""
                # Strip reasoning traces from models like deepseek-r1
                text = self._strip_thinking_tags(text)
                usage = {}
                if response.usage:
                    usage = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }
                return text, usage

            elif self.provider == "anthropic":
                response = self._client.messages.create(
                    model=self.model,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                text = response.content[0].text if response.content else ""
                usage = {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                }
                return text, usage

        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            raise

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> tuple[dict, dict]:
        """
        Call the LLM expecting a JSON response.
        Returns (parsed_dict, usage_dict).
        Raises ValueError if JSON cannot be parsed.
        """
        import re, json as _json

        # Only append JSON hint if prompt doesn't already end with a JSON instruction
        if "JSON" not in user_prompt[-200:]:
            user_prompt = user_prompt + "\n\nReturn ONLY valid JSON, no markdown."

        text, usage = self.complete(
            system_prompt,
            user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        clean = text.strip()

        # Strip thinking/reasoning blocks first
        clean = re.sub(r'<think>.*?</think>', '', clean, flags=re.DOTALL).strip()
        clean = re.sub(r'<reasoning>.*?</reasoning>', '', clean, flags=re.DOTALL).strip()

        # Strip markdown fences
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1] if lines and lines[-1].startswith("```") else lines[1:])

        # Handle truncated JSON — try to close it
        clean = clean.strip()
        try:
            return _json.loads(clean), usage
        except _json.JSONDecodeError:
            pass

        # Try extracting a JSON object
        brace = re.search(r'\{.*\}', clean, re.DOTALL)
        if brace:
            try:
                return _json.loads(brace.group(0)), usage
            except Exception:
                pass

        logger.error("LLM returned non-JSON (first 200 chars): %s", clean[:200])
        raise ValueError(f"LLM response was not valid JSON. Preview: {clean[:200]}")


# Singleton
_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client

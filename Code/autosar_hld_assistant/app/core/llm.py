"""Chat-completion client for Mistral (OpenAI-compatible API) or Azure OpenAI."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import AzureOpenAI, OpenAI

from autosar_hld_assistant.app.core.config import LLMSettings, llm_settings_from_env

log = logging.getLogger(__name__)

PROVIDERS = ("mistral", "azure")


class LLMError(RuntimeError):
    """The provider could not be reached or returned an error."""


class LLMNotConfigured(LLMError):
    """No credentials for the selected provider."""


class LLMClient:
    """Thin wrapper over the OpenAI SDK.

    Construct one per request with the settings that apply to that request;
    the object is cheap to create.
    """

    def __init__(self, settings: LLMSettings | None = None):
        self.settings = settings or llm_settings_from_env()
        self.provider = self.settings.provider
        self.model = ""
        self._client: OpenAI | AzureOpenAI | None = None

        if self.provider == "mistral" and self.settings.mistral_api_key:
            self._client = OpenAI(
                base_url=self.settings.mistral_base_url,
                api_key=self.settings.mistral_api_key,
            )
            self.model = self.settings.mistral_model
        elif self.provider == "azure" and self.settings.azure_endpoint and self.settings.azure_api_key:
            self._client = AzureOpenAI(
                azure_endpoint=self.settings.azure_endpoint,
                api_key=self.settings.azure_api_key,
                api_version=self.settings.azure_api_version,
            )
            self.model = self.settings.azure_deployment

    def is_configured(self) -> bool:
        return self._client is not None

    def describe(self) -> str:
        """Short label for the UI, e.g. 'Mistral · ministral-8b-latest'."""
        if not self.is_configured():
            return "Not configured"
        name = "Mistral" if self.provider == "mistral" else "Azure OpenAI"
        return f"{name} · {self.model}"

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        history: list[dict[str, str]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1500,
        json_mode: bool = False,
    ) -> str:
        """Send one chat completion and return the reply text.

        `history` holds earlier turns as {"role", "content"} dicts; only user
        and assistant turns are forwarded.
        """
        if self._client is None:
            raise LLMNotConfigured(f"No credentials configured for provider '{self.provider}'.")

        messages = [{"role": "system", "content": system_prompt}]
        for turn in history or []:
            if turn.get("role") in ("user", "assistant") and turn.get("content"):
                messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": user_prompt})

        options = {"response_format": {"type": "json_object"}} if json_mode else {}
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **options,
            )
        except Exception as exc:  # the SDK raises many subclasses; surface them uniformly
            raise LLMError(f"{self.describe()}: {exc}") from exc
        return response.choices[0].message.content or ""

    def chat_json(self, system_prompt: str, user_prompt: str, max_tokens: int = 6000) -> dict[str, Any] | None:
        """Ask for a JSON object (provider JSON mode) and parse it. Returns None if unusable."""
        raw = self.chat(
            system_prompt + "\n\nReply with a single JSON object and nothing else.",
            user_prompt,
            temperature=0.0,
            max_tokens=max_tokens,
            json_mode=True,
        )
        return parse_json_reply(raw)


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def parse_json_reply(raw: str) -> dict[str, Any] | None:
    """Parse a model reply that should be a JSON object.

    Tolerates ``` fences, and recovers the complete items of a reply that was
    cut off by the token limit.
    """
    text = _FENCE.sub("", raw.strip())
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = _salvage_truncated(text)
        if value is None:
            log.warning("LLM reply was not valid JSON: %.200s", raw)
            return None
        log.warning("LLM reply was cut off; kept the complete items")
    return value if isinstance(value, dict) else None


def _closers(text: str) -> str | None:
    """Brackets needed to close `text`, or None if it ends inside a string."""
    stack, in_string, escaped = [], False, False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()
    return None if in_string else "".join(reversed(stack))


def _salvage_truncated(text: str, attempts: int = 200) -> dict[str, Any] | None:
    """Cut a truncated JSON object back to its last complete item and close it."""
    end = len(text)
    for _ in range(attempts):
        end = text.rfind("}", 0, end)
        if end <= 0:
            return None
        head = text[:end + 1]
        closers = _closers(head)
        if closers is not None:
            try:
                value = json.loads(head + closers)
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                pass
    return None

"""Gemini client wrapper.

Kept deliberately thin: one class, one method (generate_json), plus retries,
spacing between calls, and a small JSON-parsing fallback when Gemini wraps
the payload in ```json fences.

The caller is responsible for prompt content. This module does not know
about jobs or scoring.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("jobhunt.llm")

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_TEMPERATURE = 0.2
# Free tier: 5 RPM → one call every 12 s keeps us just under the limit.
MIN_SPACING_S = 12.0
MAX_RETRY_WAIT_S = 60.0

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
# "Please retry in 48.05s." or the proto block "retry_delay { seconds: 48 }"
_RETRY_AFTER_RE = re.compile(r"retry in (\d+(?:\.\d+)?)\s*s", re.IGNORECASE)
_RETRY_DELAY_BLOCK_RE = re.compile(r"retry_delay\s*\{\s*seconds:\s*(\d+)", re.IGNORECASE)


class LLMError(RuntimeError):
    """Raised when Gemini fails after retries or returns unusable output."""


@dataclass
class GeminiClient:
    api_key: str | None = None
    model: str = DEFAULT_MODEL
    temperature: float = DEFAULT_TEMPERATURE
    min_spacing_s: float = MIN_SPACING_S
    max_retries: int = 3
    _last_call: float = field(default=0.0, init=False, repr=False)
    _model: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise LLMError("GEMINI_API_KEY is not set (pass api_key=... or set the env var)")

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        # Import lazily so unit tests that monkeypatch this module don't have
        # to install google-generativeai.
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        self._model = genai.GenerativeModel(
            self.model,
            generation_config={
                "temperature": self.temperature,
                "response_mime_type": "application/json",
            },
        )

    # ---- public API --------------------------------------------------------

    def generate_json(self, prompt: str, *, system: str | None = None) -> dict[str, Any]:
        """Send prompt to Gemini, parse the JSON response, return a dict.

        Retries on 429/5xx with exponential backoff. Raises LLMError if all
        attempts fail or the response isn't parseable JSON.
        """
        self._ensure_model()
        self._throttle()
        full_prompt = f"{system.strip()}\n\n{prompt}" if system else prompt

        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = self._model.generate_content(full_prompt)
                text = _extract_text(response)
                return _parse_json(text)
            except Exception as e:  # noqa: BLE001
                last_err = e
                if not _is_retryable(e):
                    raise LLMError(f"Gemini call failed (non-retryable): {e}") from e
                wait = _retry_wait_secs(e, attempt=attempt)
                log.warning("gemini retry %d/%d in %.0fs: %s", attempt + 1, self.max_retries, wait, e)
                time.sleep(wait)
        raise LLMError(f"Gemini call failed after {self.max_retries} retries: {last_err}")

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_spacing_s:
            time.sleep(self.min_spacing_s - elapsed)
        self._last_call = time.monotonic()


# ---- helpers ---------------------------------------------------------------


def _extract_text(response: Any) -> str:
    """Pull the text payload out of a Gemini response object."""
    text = getattr(response, "text", None)
    if text:
        return str(text)
    # Older SDKs expose candidates[0].content.parts[0].text
    try:
        return response.candidates[0].content.parts[0].text  # type: ignore[attr-defined]
    except Exception as e:  # noqa: BLE001
        raise LLMError(f"Could not extract text from Gemini response: {e}") from e


def _parse_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise LLMError("Gemini returned empty text")
    # Strip ```json fences if present.
    stripped = _FENCE_RE.sub("", raw).strip()
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as e:
        # Try to pluck out the first {...} block; Gemini sometimes adds prose.
        start, end = stripped.find("{"), stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(stripped[start : end + 1])
            except json.JSONDecodeError:
                raise LLMError(f"Could not parse Gemini JSON: {e}; text={stripped[:200]!r}") from e
        else:
            raise LLMError(f"Could not parse Gemini JSON: {e}; text={stripped[:200]!r}") from e
    if not isinstance(data, dict):
        raise LLMError(f"Gemini returned non-object JSON: {type(data).__name__}")
    return data


def _retry_wait_secs(exc: Exception, *, attempt: int = 0) -> float:
    """Return seconds to wait before the next retry.

    Prefers the retry_delay the API embeds in 429 responses; falls back to
    exponential backoff (2, 4, 8 …). Either way capped at MAX_RETRY_WAIT_S.
    """
    s = str(exc)
    for pattern in (_RETRY_AFTER_RE, _RETRY_DELAY_BLOCK_RE):
        m = pattern.search(s)
        if m:
            return min(float(m.group(1)), MAX_RETRY_WAIT_S)
    return min(2 ** (attempt + 1), MAX_RETRY_WAIT_S)


def _is_retryable(exc: Exception) -> bool:
    s = str(exc).lower()
    # Google SDK surfaces quota / server errors as different classes by version.
    # Match by message to stay SDK-agnostic.
    return any(tok in s for tok in ("429", "rate limit", "resource exhausted", "500", "502", "503", "504", "unavailable"))

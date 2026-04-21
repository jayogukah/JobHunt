"""Source protocol and shared HTTP helpers."""

from __future__ import annotations

import time
from typing import Any, Protocol

import httpx

from src.models import Job

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
DEFAULT_HEADERS = {
    "User-Agent": "JobHunt/0.1 (personal job discovery; +https://github.com)",
    "Accept": "application/json, text/xml, */*",
}


class Source(Protocol):
    name: str

    def fetch(self, targets: list[str], search: dict[str, Any]) -> list[Job]: ...


def http_get_json(url: str, params: dict[str, Any] | None = None, retries: int = 3) -> Any:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT, headers=DEFAULT_HEADERS, follow_redirects=True) as c:
                r = c.get(url, params=params)
                r.raise_for_status()
                return r.json()
        except (httpx.HTTPError, ValueError) as e:
            last_exc = e
            time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last_exc}")


def http_get_text(url: str, params: dict[str, Any] | None = None, retries: int = 3) -> str:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT, headers=DEFAULT_HEADERS, follow_redirects=True) as c:
                r = c.get(url, params=params)
                r.raise_for_status()
                return r.text
        except httpx.HTTPError as e:
            last_exc = e
            time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last_exc}")

"""Config loading. Reads YAML from ./config/ and returns plain dicts.

Kept deliberately simple: YAML is the source of truth, not pydantic, because
the shape of targets.yaml is ATS-name -> list[str] and profile.yaml is free-
form content the renderer treats as data.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at top of {path}, got {type(data).__name__}")
    return data


def load_profile() -> dict[str, Any]:
    return _load(CONFIG_DIR / "profile.yaml")


def load_targets() -> dict[str, list[str]]:
    raw = _load(CONFIG_DIR / "targets.yaml")
    out: dict[str, list[str]] = {}
    for ats, slugs in raw.items():
        if slugs is None:
            out[ats] = []
        elif isinstance(slugs, list):
            out[ats] = [str(s).strip() for s in slugs if str(s).strip()]
        else:
            raise ValueError(f"targets.yaml: {ats!r} must be a list, got {type(slugs).__name__}")
    return out


def load_search() -> dict[str, Any]:
    return _load(CONFIG_DIR / "search.yaml")


def env(key: str, default: str | None = None) -> str | None:
    val = os.environ.get(key, default)
    return val if val else default

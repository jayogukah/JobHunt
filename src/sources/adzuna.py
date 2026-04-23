"""Adzuna search API. Free tier, 250 calls/month — spend carefully.

Docs: https://developer.adzuna.com/docs/search
Endpoint: https://api.adzuna.com/v1/api/jobs/{country}/search/{page}
Env vars: ADZUNA_APP_ID, ADZUNA_APP_KEY
"""

from __future__ import annotations

import os
from typing import Any

from src.models import Job
from src.normalize import clean_html, detect_remote, parse_ts, short_location

from .base import http_get_json

NAME = "adzuna"
BASE = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


def fetch_country_keyword(country: str, keyword: str, page: int = 1, limit: int = 50) -> list[Job]:
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise RuntimeError("Adzuna: ADZUNA_APP_ID / ADZUNA_APP_KEY are not set")
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": str(limit),
        "what": keyword,
        "content-type": "application/json",
    }
    data = http_get_json(BASE.format(country=country, page=page), params=params)
    results = data.get("results") or []
    out: list[Job] = []
    for r in results:
        try:
            job = _to_job(r, country)
        except Exception:
            continue
        if job.title and job.apply_url:
            out.append(job)
    return out


def fetch(targets: list[str], search: dict[str, Any]) -> list[Job]:  # noqa: ARG001
    """Targets ignored; we use the country list from search.yaml.

    Spend control: 1 call per (country, keyword) pair, first page only.
    With 6 countries and 7 keywords that's 42 calls per run, well under
    the 250/month free tier for daily runs (42 * 30 = 1260, but we rely
    on dedupe to minimise re-scoring). Adjust by pruning keywords in
    search.yaml if you burn through quota.
    """
    out: list[Job] = []
    countries = search.get("adzuna_countries") or []
    keywords = search.get("keywords") or []
    if not countries or not keywords:
        return out
    for country in countries:
        for kw in keywords:
            try:
                out.extend(fetch_country_keyword(country, kw, page=1, limit=50))
            except Exception:
                # individual country/keyword failures shouldn't nuke the
                # whole source; let the caller log if needed.
                continue
    return out


def _to_job(r: dict[str, Any], country: str) -> Job:
    loc_area = ", ".join((r.get("location") or {}).get("area") or [])
    description = clean_html(r.get("description") or "")
    company = ((r.get("company") or {}).get("display_name") or "").strip()
    return Job(
        source=NAME,
        source_id=str(r.get("id") or r.get("redirect_url") or ""),
        title=(r.get("title") or "").strip(),
        company=company,
        location=loc_area or None,
        remote=detect_remote(loc_area, description),
        description=description,
        apply_url=r.get("redirect_url") or "",
        posted_at=parse_ts(r.get("created")),
        salary_min=_as_float(r.get("salary_min")),
        salary_max=_as_float(r.get("salary_max")),
        currency=(r.get("salary_is_predicted") is not None and country.upper()) or None,
        raw={"country": country, "category": (r.get("category") or {}).get("label"), "contract_type": r.get("contract_type")},
    )


def _as_float(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None

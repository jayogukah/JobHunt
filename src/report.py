"""Daily brief rendering.

Takes the scored + tailored jobs produced by main.py and writes:
  reports/{YYYY-MM-DD}/brief.md
  reports/{YYYY-MM-DD}/jobs.json    (flat, PWA-friendly)
  reports/{YYYY-MM-DD}/meta.json    (run-level summary)
  reports/run_log.csv               (appended)
Also mirrors jobs.json, meta.json, and the tailored/ folder to
reports/latest/ so consumers (e.g. the JobHunt PWA) can hit a stable URL.
"""

from __future__ import annotations

import csv
import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.models import ScoredJob, SourceResult

log = logging.getLogger("jobhunt.report")

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
REPORTS_ROOT = Path(__file__).resolve().parent.parent / "reports"


@dataclass
class RunStats:
    run_date: str
    total_fetched: int = 0
    fresh_count: int = 0
    dedup_skip: int = 0
    heuristic_evaluated: int = 0
    heuristic_passed: int = 0
    gemini_scored: int = 0
    top_n: int = 0
    min_heuristic: float = 0.4
    min_final: float = 0.7
    source_failures: list[str] = field(default_factory=list)
    duration_s: float = 0.0
    partial_reason: str | None = None


def _posted_age(s: ScoredJob) -> str:
    if not s.job.posted_at:
        return "unknown"
    now = datetime.now(tz=timezone.utc)
    days = max(0, (now - s.job.posted_at).days)
    if days == 0:
        return "today"
    if days == 1:
        return "1 day ago"
    if days < 30:
        return f"{days} days ago"
    return f"{days // 30} month(s) ago"


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=False,
        lstrip_blocks=False,
    )
    env.filters["posted_age"] = _posted_age
    return env


def write_brief(
    run_date: date,
    results: list[SourceResult],
    top_n: list[ScoredJob],
    close_misses: list[ScoredJob],
    stats: RunStats,
) -> Path:
    """Render brief.md.j2 to reports/{date}/brief.md and return the path."""
    day_dir = REPORTS_ROOT / run_date.isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)
    out = day_dir / "brief.md"

    env = _env()
    tpl = env.get_template("brief.md.j2")

    text = tpl.render(
        run_date=run_date.isoformat(),
        results=results,
        top_n=top_n,
        close_misses=close_misses,
        total_fetched=stats.total_fetched,
        fresh_count=stats.fresh_count,
        dedup_skip=stats.dedup_skip,
        heuristic_evaluated=stats.heuristic_evaluated,
        heuristic_passed=stats.heuristic_passed,
        gemini_scored=stats.gemini_scored,
        min_heuristic=stats.min_heuristic,
        min_final=stats.min_final,
        partial_reason=stats.partial_reason,
        duration_s=round(stats.duration_s, 1),
    )
    out.write_text(text, encoding="utf-8")
    log.info("wrote brief: %s", out)
    return out


def write_jobs_json(run_date: date, scored: list[ScoredJob]) -> Path:
    day_dir = REPORTS_ROOT / run_date.isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)
    out = day_dir / "jobs.json"
    payload = [_scored_to_flat(s, run_date) for s in scored]
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    log.info("wrote jobs.json: %s (%d rows)", out, len(payload))
    return out


def write_meta_json(
    run_date: date,
    results: list[SourceResult],
    stats: "RunStats",
) -> Path:
    """Run-level summary the PWA reads alongside jobs.json."""
    day_dir = REPORTS_ROOT / run_date.isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)
    out = day_dir / "meta.json"
    payload = {
        "run_date": stats.run_date,
        "total_fetched": stats.total_fetched,
        "total_scored": stats.gemini_scored or stats.heuristic_passed,
        "heuristic_passed": stats.heuristic_passed,
        "gemini_scored": stats.gemini_scored,
        "top_n": stats.top_n,
        "min_heuristic": stats.min_heuristic,
        "min_final": stats.min_final,
        "duration_s": round(stats.duration_s, 2),
        "partial_reason": stats.partial_reason,
        "sources": {
            r.source: {
                "count": len(r.jobs),
                "status": "ok" if r.ok else "failed",
                "duration_s": r.duration_s,
                "error": r.error or None,
            }
            for r in results
        },
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log.info("wrote meta.json: %s", out)
    return out


def mirror_to_latest(run_date: date) -> Path:
    """Copy jobs.json, meta.json, and tailored/ from reports/{date}/ to
    reports/latest/ so consumers (PWA) have a stable URL.

    We use a plain directory (not a symlink) because GitHub raw URLs do not
    resolve symlinks consistently.
    """
    src_dir = REPORTS_ROOT / run_date.isoformat()
    latest = REPORTS_ROOT / "latest"
    latest.mkdir(parents=True, exist_ok=True)

    for name in ("jobs.json", "meta.json", "brief.md"):
        src = src_dir / name
        if src.exists():
            shutil.copyfile(src, latest / name)

    tailored_src = src_dir / "tailored"
    tailored_dst = latest / "tailored"
    if tailored_src.exists():
        if tailored_dst.exists():
            shutil.rmtree(tailored_dst)
        shutil.copytree(tailored_src, tailored_dst)
    log.info("mirrored run artefacts to %s", latest)
    return latest


def append_run_log(stats: RunStats) -> Path:
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    out = REPORTS_ROOT / "run_log.csv"
    new = not out.exists()
    with out.open("a", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow([
                "run_date", "total_fetched", "fresh", "dedup_skip",
                "heuristic_evaluated", "heuristic_passed",
                "gemini_scored", "top_n", "duration_s", "source_failures",
                "partial_reason",
            ])
        w.writerow([
            stats.run_date, stats.total_fetched, stats.fresh_count, stats.dedup_skip,
            stats.heuristic_evaluated, stats.heuristic_passed,
            stats.gemini_scored, stats.top_n, round(stats.duration_s, 2),
            ";".join(stats.source_failures),
            stats.partial_reason or "",
        ])
    return out


def _scored_to_flat(s: ScoredJob, run_date: date) -> dict[str, Any]:
    """Flat, PWA-consumable representation. Keeps only fields the UI shows.

    cv_path is returned as a path relative to reports/{date}/ so consumers
    that host reports via a CDN or raw-github URL can resolve it with a
    simple join.
    """
    g = s.gemini
    cv_rel: str | None = None
    if s.tailored_cv_path:
        p = Path(s.tailored_cv_path)
        # Normalise to "tailored/{file}.docx" even if a full filesystem path
        # was stored.
        cv_rel = f"tailored/{p.name}" if p.name.lower().endswith(".docx") else str(p)

    return {
        # Identification
        "source": s.job.source,
        "source_id": s.job.source_id,
        "run_date": run_date.isoformat(),
        # Display fields
        "title": s.job.title,
        "company": s.job.company,
        "location": s.job.location,
        "remote": s.job.remote,
        "apply_url": s.job.apply_url,
        "posted_at": s.job.posted_at.isoformat() if s.job.posted_at else None,
        "salary_min": s.job.salary_min,
        "salary_max": s.job.salary_max,
        "currency": s.job.currency,
        # Description is useful for search/debug but is the largest field.
        # Keep the first 2k chars to stay well under a few hundred KB per file.
        "description": (s.job.description or "")[:2000],
        # Scores
        "heuristic_score": round(s.heuristic.score, 4),
        "fit_score": round(g.fit_score, 4) if g else None,
        # Gemini signals (null if scoring skipped)
        "sponsorship_likely": g.sponsorship_likely if g else None,
        "strengths": g.strengths if g else [],
        "gaps": g.gaps if g else [],
        "red_flags": g.red_flags if g else [],
        "why_apply": g.why_apply if g else "",
        "why_skip": g.why_skip if g else "",
        # Tailored CV (null unless a DOCX was generated)
        "cv_path": cv_rel,
    }

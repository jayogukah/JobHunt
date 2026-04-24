"""Daily brief rendering (step 10).

Takes the scored + tailored jobs produced by main.py and writes:
  reports/{YYYY-MM-DD}/brief.md
  reports/{YYYY-MM-DD}/jobs.json
Also appends a row to reports/run_log.csv with run stats.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import asdict, dataclass, field
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
    payload = [_scored_to_dict(s) for s in scored]
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    log.info("wrote jobs.json: %s (%d rows)", out, len(payload))
    return out


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


def _scored_to_dict(s: ScoredJob) -> dict[str, Any]:
    d: dict[str, Any] = {
        "job": {
            "source": s.job.source,
            "source_id": s.job.source_id,
            "title": s.job.title,
            "company": s.job.company,
            "location": s.job.location,
            "remote": s.job.remote,
            "apply_url": s.job.apply_url,
            "posted_at": s.job.posted_at.isoformat() if s.job.posted_at else None,
        },
        "heuristic": asdict(s.heuristic) if hasattr(s.heuristic, "__dataclass_fields__") else s.heuristic.model_dump(),
        "gemini": s.gemini.model_dump() if s.gemini else None,
        "tailored_cv_path": s.tailored_cv_path,
        "final_score": s.final_score,
    }
    return d

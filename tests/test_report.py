"""Tests for the daily brief and run log."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path

from src.models import GeminiScore, HeuristicScore, Job, ScoredJob, SourceResult
from src.report import RunStats, append_run_log, write_brief, write_jobs_json


def _scored(company: str, title: str, fit: float, sponsor: str = "yes") -> ScoredJob:
    job = Job(
        source="greenhouse",
        source_id=company + ":" + title,
        title=title,
        company=company,
        location="Remote - EU",
        remote=True,
        description="desc",
        apply_url=f"https://example.com/{company}",
        posted_at=datetime(2025, 4, 20, tzinfo=timezone.utc),
    )
    h = HeuristicScore(score=0.7, keyword_hits=["AI"])
    g = GeminiScore(
        fit_score=fit,
        sponsorship_likely=sponsor,
        strengths=["tooling overlap"],
        gaps=["no UK years"],
        red_flags=[],
        why_apply="Strong overlap on Python and Gemini API.",
        why_skip="" if fit >= 0.6 else "Below bar on sponsorship.",
    )
    return ScoredJob(job=job, heuristic=h, gemini=g, tailored_cv_path="reports/2025-04-23/tailored/example.docx")


def test_write_brief_renders_sections(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("src.report.REPORTS_ROOT", tmp_path)
    s1 = _scored("Canonical", "Senior AI Engineer", 0.85)
    s2 = _scored("Monzo", "Automation Engineer", 0.78)
    close = _scored("Stripe", "Platform Engineer", 0.55)
    results = [
        SourceResult(source="greenhouse", jobs=[s1.job, s2.job], duration_s=0.5),
        SourceResult(source="lever", jobs=[], error="boom", duration_s=0.1),
    ]
    stats = RunStats(run_date="2025-04-23", total_fetched=2, heuristic_evaluated=2, heuristic_passed=2, gemini_scored=2, top_n=2)
    path = write_brief(date(2025, 4, 23), results, [s1, s2], [close], stats)
    text = path.read_text(encoding="utf-8")

    assert "JobHunt brief, 2025-04-23" in text
    assert "Canonical" in text and "Monzo" in text
    assert "Stripe" in text  # close miss row
    assert "boom" in text   # source failure surfaced
    assert "greenhouse" in text and "lever" in text
    assert "Strong overlap" in text  # why_apply carried through
    assert "tailored/example.docx" in text
    assert "0.85" in text


def test_write_brief_handles_empty_top_picks(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("src.report.REPORTS_ROOT", tmp_path)
    stats = RunStats(run_date="2025-04-23")
    path = write_brief(date(2025, 4, 23), [], [], [], stats)
    text = path.read_text(encoding="utf-8")
    assert "No jobs cleared the tailoring threshold" in text


def test_write_jobs_json_round_trip(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("src.report.REPORTS_ROOT", tmp_path)
    s = _scored("Canonical", "Senior AI Engineer", 0.85)
    path = write_jobs_json(date(2025, 4, 23), [s])
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["job"]["company"] == "Canonical"
    assert data[0]["final_score"] == 0.85
    assert data[0]["gemini"]["sponsorship_likely"] == "yes"


def test_append_run_log_writes_header_once(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("src.report.REPORTS_ROOT", tmp_path)
    stats = RunStats(run_date="2025-04-23", total_fetched=10, fresh_count=6, top_n=3, duration_s=12.3)
    append_run_log(stats)
    append_run_log(stats)
    path = tmp_path / "run_log.csv"
    rows = list(csv.reader(path.open("r", encoding="utf-8")))
    assert rows[0][0] == "run_date"  # header
    assert rows[1][0] == "2025-04-23"
    assert rows[2][0] == "2025-04-23"
    assert len(rows) == 3  # header + 2 rows, no duplicate header

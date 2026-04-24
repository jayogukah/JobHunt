"""Tests for the main.py orchestration changes: the Gemini cap, the time
budget, and the try/finally fallback that still writes a brief on crash.

All tests stub the network boundary. No real LLM or HTTP calls.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

import src.main as main_mod
from src.models import HeuristicScore, Job, ScoredJob
from src.main import split_llm_eligible


def _job(title: str = "Senior AI Engineer", apply_url: str | None = None) -> Job:
    return Job(
        source="greenhouse",
        source_id=title,
        title=title,
        company="Example Co",
        location="Remote",
        remote=True,
        description="Python, Gemini API. Sponsorship offered.",
        apply_url=apply_url or f"https://example.com/{title.lower().replace(' ', '-')}",
    )


def _scored(heuristic: float) -> ScoredJob:
    return ScoredJob(job=_job(f"Role {heuristic}"), heuristic=HeuristicScore(score=heuristic))


def test_split_llm_eligible_keeps_top_by_heuristic():
    scored = [_scored(0.4), _scored(0.9), _scored(0.6), _scored(0.8), _scored(0.5)]
    eligible, heuristic_only = split_llm_eligible(scored, max_llm=2)
    assert [s.heuristic.score for s in eligible] == [0.9, 0.8]
    assert [s.heuristic.score for s in heuristic_only] == [0.6, 0.5, 0.4]


def test_split_llm_eligible_cap_larger_than_list():
    scored = [_scored(0.9), _scored(0.5)]
    eligible, heuristic_only = split_llm_eligible(scored, max_llm=10)
    assert [s.heuristic.score for s in eligible] == [0.9, 0.5]
    assert heuristic_only == []


def test_split_llm_eligible_zero_cap_defers_all():
    scored = [_scored(0.9), _scored(0.5)]
    eligible, heuristic_only = split_llm_eligible(scored, max_llm=0)
    assert eligible == []
    assert [s.heuristic.score for s in heuristic_only] == [0.9, 0.5]


# --- end-to-end main() with stubbed sources -------------------------------


def _stub_sources(monkeypatch, jobs: list[Job]) -> None:
    from src.sources import greenhouse, lever

    monkeypatch.setattr(
        greenhouse,
        "http_get_json",
        lambda url, params=None: {
            "jobs": [
                {
                    "id": i,
                    "title": j.title,
                    "content": j.description,
                    "absolute_url": j.apply_url,
                    "updated_at": "2026-04-01T00:00:00Z",
                    "location": {"name": j.location},
                    "offices": [],
                    "departments": [],
                    "company_name": j.company,
                }
                for i, j in enumerate(jobs)
            ]
        },
    )
    monkeypatch.setattr(lever, "http_get_json", lambda url, params=None: [])


def _isolate_filesystem(tmp_path: Path, monkeypatch) -> None:
    """Point all IO at tmp_path so tests don't touch reports/ or db/."""
    monkeypatch.setattr("src.report.REPORTS_ROOT", tmp_path / "reports")
    monkeypatch.setattr("src.dedupe.DEFAULT_DB", tmp_path / "seen.sqlite")


def test_dry_run_always_writes_brief(tmp_path: Path, monkeypatch):
    _isolate_filesystem(tmp_path, monkeypatch)
    jobs = [_job("Senior AI Automation Engineer")]
    _stub_sources(monkeypatch, jobs)
    # Ensure we don't accidentally email from a test.
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    rc = main_mod.main(["--dry-run", "--only", "greenhouse,lever", "--no-email"])
    assert rc == 0
    today = date.today().isoformat()
    brief = tmp_path / "reports" / today / "brief.md"
    assert brief.exists(), "brief.md must exist after a successful dry-run"
    assert "PARTIAL RUN" not in brief.read_text(encoding="utf-8")


def test_mid_run_crash_still_writes_partial_brief(tmp_path: Path, monkeypatch):
    _isolate_filesystem(tmp_path, monkeypatch)
    jobs = [_job("Senior AI Automation Engineer")]
    _stub_sources(monkeypatch, jobs)

    # Simulate a crash during heuristic scoring: monkeypatch filter_and_score
    # to raise. The finally block should still produce a brief.
    def boom(*a, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr("src.main.filter_and_score", boom)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)

    rc = main_mod.main(["--dry-run", "--only", "greenhouse,lever", "--no-email"])
    assert rc == 0

    today = date.today().isoformat()
    brief = tmp_path / "reports" / today / "brief.md"
    assert brief.exists()
    text = brief.read_text(encoding="utf-8")
    assert "PARTIAL RUN" in text
    assert "boom" in text


def test_sigterm_triggers_partial_brief(tmp_path: Path, monkeypatch):
    _isolate_filesystem(tmp_path, monkeypatch)
    jobs = [_job("Senior AI Automation Engineer")]
    _stub_sources(monkeypatch, jobs)

    def interrupt(*a, **kw):
        # Simulate SIGTERM being delivered mid-pipeline.
        raise KeyboardInterrupt("received signal 15")

    monkeypatch.setattr("src.main.filter_and_score", interrupt)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)

    rc = main_mod.main(["--dry-run", "--only", "greenhouse,lever", "--no-email"])
    assert rc == 0

    today = date.today().isoformat()
    brief = tmp_path / "reports" / today / "brief.md"
    assert brief.exists()
    assert "PARTIAL RUN" in brief.read_text(encoding="utf-8")


def test_partial_reason_appears_in_run_log(tmp_path: Path, monkeypatch):
    _isolate_filesystem(tmp_path, monkeypatch)
    _stub_sources(monkeypatch, [_job("Senior AI Automation Engineer")])
    monkeypatch.setattr("src.main.filter_and_score", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("oops")))
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    main_mod.main(["--dry-run", "--only", "greenhouse,lever", "--no-email"])
    log_path = tmp_path / "reports" / "run_log.csv"
    assert log_path.exists()
    rows = log_path.read_text(encoding="utf-8").splitlines()
    header = rows[0].split(",")
    assert "partial_reason" in header
    idx = header.index("partial_reason")
    assert any("oops" in row.split(",")[idx] for row in rows[1:])

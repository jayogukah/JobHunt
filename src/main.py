"""JobHunt entrypoint.

Pipeline (when fully run):
  1. Fetch from all enabled sources
  2. Normalize, then split via SeenStore into fresh vs previously-seen
  3. Heuristic prefilter + drop below min_heuristic_score
  4. Gemini deep scoring for the top-heuristic survivors (capped)
  5. Rank, select top N, tailor via Gemini, render DOCX
  6. Write brief.md, jobs.json, run_log.csv. Optionally email.

Everything from step 2 onward runs inside a try/finally that writes the
brief + sends email even if we crash, time out, or get SIGTERMed by the
GitHub Actions runner. Partial results are labelled as such in the brief.

Flags:
  --dry-run            Fetch + heuristic only. No Gemini calls, no DOCX, no email.
  --only NAMES         Comma-separated source names (e.g. greenhouse,lever).
  --limit N            Cap jobs per source to at most N (useful for local testing).
  --no-tailor          Skip DOCX generation even for top picks.
  --no-email           Skip the email-brief step regardless of Gmail env vars.
  --verbose            DEBUG logging.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import smtplib
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from email.message import EmailMessage
from typing import Any, Callable

from src.config import load_profile, load_search, load_targets
from src.dedupe import SeenStore
from src.models import Job, ScoredJob, SourceResult
from src.report import RunStats, append_run_log, write_brief, write_jobs_json
from src.score import filter_and_score, score_job_llm
from src.sources import (
    adzuna,
    arbeitnow,
    ashby,
    greenhouse,
    hn_whoishiring,
    lever,
    personio,
    remotive,
    workable,
)

log = logging.getLogger("jobhunt")

# Defaults. Overridable via scoring config in search.yaml.
DEFAULT_MAX_GEMINI_SCORED = 40
DEFAULT_TIME_BUDGET_S = 1200  # 20 minutes; Actions timeout is 25.


@dataclass
class Registry:
    """Maps source name -> (targets_key_in_targets_yaml, fetch_fn)."""

    fetchers: dict[str, tuple[str, Callable[[list[str], dict[str, Any]], list[Job]]]] = field(default_factory=dict)
    # For keyword-based sources we use a synthetic "<keyword>" targets key
    # so the config loader does not need to know about them.
    keyword_only: set[str] = field(default_factory=set)

    def register(
        self,
        name: str,
        targets_key: str,
        fn: Callable[[list[str], dict[str, Any]], list[Job]],
        *,
        keyword_only: bool = False,
    ) -> None:
        self.fetchers[name] = (targets_key, fn)
        if keyword_only:
            self.keyword_only.add(name)


def default_registry() -> Registry:
    reg = Registry()
    reg.register(greenhouse.NAME, "greenhouse", greenhouse.fetch)
    reg.register(lever.NAME, "lever", lever.fetch)
    reg.register(ashby.NAME, "ashby", ashby.fetch)
    reg.register(workable.NAME, "workable", workable.fetch)
    reg.register(personio.NAME, "personio", personio.fetch)
    # Keyword-based sources: no targets.yaml entry needed.
    reg.register(remotive.NAME, "_keyword", remotive.fetch, keyword_only=True)
    reg.register(arbeitnow.NAME, "_keyword", arbeitnow.fetch, keyword_only=True)
    reg.register(adzuna.NAME, "_keyword", adzuna.fetch, keyword_only=True)
    reg.register(hn_whoishiring.NAME, "_keyword", hn_whoishiring.fetch, keyword_only=True)
    return reg


def run_sources(
    registry: Registry,
    targets: dict[str, list[str]],
    search: dict[str, Any],
    only: set[str] | None = None,
    limit: int = 0,
) -> list[SourceResult]:
    results: list[SourceResult] = []
    for name, (targets_key, fn) in registry.fetchers.items():
        if only and name not in only:
            continue
        if name in registry.keyword_only:
            slugs: list[str] = []  # keyword-only sources ignore targets
            configured = True
        else:
            slugs = targets.get(targets_key, [])
            configured = bool(slugs)
        if not configured:
            results.append(SourceResult(source=name, jobs=[], error="no targets configured"))
            continue
        t0 = time.monotonic()
        try:
            jobs = fn(slugs, search)
            if limit and len(jobs) > limit:
                jobs = jobs[:limit]
            dur = round(time.monotonic() - t0, 2)
            results.append(SourceResult(source=name, jobs=jobs, duration_s=dur))
            log.info(json.dumps({"event": "source_done", "source": name, "count": len(jobs), "duration_s": dur}))
        except Exception as e:  # noqa: BLE001
            dur = round(time.monotonic() - t0, 2)
            results.append(SourceResult(source=name, jobs=[], error=str(e), duration_s=dur))
            log.warning(json.dumps({"event": "source_failed", "source": name, "error": str(e)}))
    return results


def select_top_n_and_close(
    scored: list[ScoredJob],
    top_n: int,
    min_final_for_apply: float,
) -> tuple[list[ScoredJob], list[ScoredJob]]:
    """Return (top_n, close_misses) both sorted by final_score descending."""
    ranked = sorted(scored, key=lambda s: s.final_score, reverse=True)
    top = [s for s in ranked if s.final_score >= min_final_for_apply][:top_n]
    top_ids = {id(s) for s in top}
    close = [s for s in ranked if 0.5 <= s.final_score < min_final_for_apply and id(s) not in top_ids][:10]
    return top, close


def split_llm_eligible(
    scored_jobs: list[ScoredJob], max_llm: int
) -> tuple[list[ScoredJob], list[ScoredJob]]:
    """Sort by heuristic score desc; return (eligible_for_llm, heuristic_only).

    Eligible are the top `max_llm` by heuristic score. The rest keep their
    heuristic score as their final score and never see Gemini.
    """
    ranked = sorted(scored_jobs, key=lambda s: s.heuristic.score, reverse=True)
    if max_llm <= 0:
        return [], ranked
    return ranked[:max_llm], ranked[max_llm:]


def _tailor_and_render(top: list[ScoredJob], profile: dict[str, Any], run_date: date, client) -> None:
    # Import lazily so --dry-run and --no-tailor don't pull in google-generativeai.
    from src.render import render_cv
    from src.tailor import tailor_cv

    for s in top:
        try:
            tailored = tailor_cv(client, s.job, profile)
        except Exception as e:  # noqa: BLE001
            log.warning(json.dumps({"event": "tailor_failed", "company": s.job.company, "title": s.job.title, "error": str(e)}))
            continue
        try:
            out = render_cv(s.job, profile, tailored, run_date=run_date)
            s.tailored_cv_path = str(out)
        except Exception as e:  # noqa: BLE001
            log.warning(json.dumps({"event": "render_failed", "company": s.job.company, "title": s.job.title, "error": str(e)}))


def _maybe_email(brief_path, run_date: date) -> None:
    to_addr = os.environ.get("GMAIL_TO_ADDRESS")
    from_addr = os.environ.get("GMAIL_FROM_ADDRESS") or to_addr
    app_pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not (to_addr and from_addr and app_pw):
        log.info("email skipped (GMAIL_* secrets not all set)")
        return
    body = brief_path.read_text(encoding="utf-8")
    msg = EmailMessage()
    msg["Subject"] = f"JobHunt brief {run_date.isoformat()}"
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(from_addr, app_pw)
            s.send_message(msg)
        log.info("emailed brief to %s", to_addr)
    except Exception as e:  # noqa: BLE001
        log.warning("email failed: %s", e)


def _install_sigterm_as_interrupt() -> None:
    """Turn SIGTERM into KeyboardInterrupt so `try/finally` fires cleanly.

    GitHub Actions sends SIGTERM when `timeout-minutes` is exceeded, then
    SIGKILL 10s later. Default SIGTERM handling in Python just terminates
    the process immediately, which skips `finally` blocks. Re-raising as
    KeyboardInterrupt lets our finally block write the partial brief.
    """

    def _handler(signum, frame):  # noqa: ARG001
        raise KeyboardInterrupt(f"received signal {signum}")

    try:
        signal.signal(signal.SIGTERM, _handler)
    except ValueError:
        # Happens if called outside the main thread (e.g. under pytest threads).
        pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="JobHunt daily pipeline")
    p.add_argument("--dry-run", action="store_true", help="Fetch + heuristic only. No Gemini, no DOCX, no email.")
    p.add_argument("--only", type=str, default="", help="Comma-separated source names (e.g. greenhouse,lever).")
    p.add_argument("--limit", type=int, default=0, help="Cap jobs per source (0 = no cap).")
    p.add_argument("--no-tailor", action="store_true", help="Skip DOCX generation even for top picks.")
    p.add_argument("--no-email", action="store_true", help="Skip the email-brief step.")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
    )
    _install_sigterm_as_interrupt()
    t_start = time.monotonic()
    run_date = date.today()

    profile = load_profile()
    targets = load_targets()
    search = load_search()
    ctx = profile.get("context") or {}
    only = {s.strip() for s in args.only.split(",") if s.strip()} or None

    scoring_cfg = search.get("scoring") or {}
    min_heur = float(scoring_cfg.get("min_heuristic_score", 0.4))
    min_final = float(scoring_cfg.get("min_final_score_for_apply", 0.7))
    top_n_cap = int(scoring_cfg.get("top_n_for_tailoring", 7))
    max_llm = int(scoring_cfg.get("max_gemini_scored", DEFAULT_MAX_GEMINI_SCORED))
    time_budget = float(scoring_cfg.get("time_budget_seconds", DEFAULT_TIME_BUDGET_S))
    dedupe_days = int(search.get("dedupe_skip_days", 14))

    # State that the finally block reads. Pre-populated so partial runs can
    # still produce a brief.
    results: list[SourceResult] = []
    all_jobs: list[Job] = []
    fresh: list[Job] = []
    skipped: list[Job] = []
    scored_pairs: list[tuple] = []
    passed: list[tuple] = []
    scored_jobs: list[ScoredJob] = []
    top: list[ScoredJob] = []
    close: list[ScoredJob] = []
    partial_reason: str | None = None
    brief_path = None

    try:
        # 1. fetch
        registry = default_registry()
        results = run_sources(registry, targets, search, only=only, limit=args.limit)
        all_jobs = [j for r in results for j in r.jobs]

        # 2. dedupe
        with SeenStore() as store:
            fresh, skipped = store.partition(all_jobs, within_days=dedupe_days)
        log.info(json.dumps({"event": "dedupe_done", "fresh": len(fresh), "skipped_seen": len(skipped)}))

        # 3. heuristic prefilter
        scored_pairs = filter_and_score(fresh, search, ctx)
        passed = [(j, h) for j, h in scored_pairs if h.score >= min_heur]
        scored_jobs = [ScoredJob(job=j, heuristic=h) for j, h in passed]
        log.info(json.dumps({
            "event": "heuristic_done", "evaluated": len(scored_pairs), "passed": len(passed),
        }))

        # 4. Gemini deep scoring — capped and time-budgeted
        gemini_client = None
        if args.dry_run:
            log.info(json.dumps({"event": "dry_run", "note": "skipping Gemini scoring and tailoring"}))
        else:
            try:
                from src.llm import GeminiClient

                gemini_client = GeminiClient()
            except Exception as e:  # noqa: BLE001
                log.warning("Gemini client init failed: %s; continuing with heuristic only", e)
                partial_reason = f"gemini_init_failed: {e}"

        llm_jobs, heuristic_only = split_llm_eligible(scored_jobs, max_llm)
        if gemini_client is not None and llm_jobs:
            log.info(json.dumps({
                "event": "gemini_begin",
                "eligible": len(llm_jobs),
                "cap": max_llm,
                "deferred_to_heuristic": len(heuristic_only),
                "budget_s": time_budget,
            }))
            for i, sj in enumerate(llm_jobs, start=1):
                elapsed = time.monotonic() - t_start
                if elapsed > time_budget:
                    partial_reason = (
                        f"time_budget_exceeded after {i - 1}/{len(llm_jobs)} LLM scores "
                        f"(elapsed {elapsed:.0f}s > budget {time_budget:.0f}s)"
                    )
                    log.warning(json.dumps({"event": "gemini_time_budget", "scored": i - 1, "remaining": len(llm_jobs) - (i - 1)}))
                    break
                try:
                    sj.gemini = score_job_llm(gemini_client, sj.job, profile)
                except Exception as e:  # noqa: BLE001
                    log.warning(json.dumps({
                        "event": "gemini_score_failed",
                        "company": sj.job.company,
                        "title": sj.job.title,
                        "error": str(e),
                    }))

        # 5. Rank and tailor top N
        top, close = select_top_n_and_close(scored_jobs, top_n=top_n_cap, min_final_for_apply=min_final)
        if not args.dry_run and not args.no_tailor and gemini_client is not None and top:
            # Guard tailoring with the same budget so a slow tail-end doesn't
            # kill the finally block.
            elapsed = time.monotonic() - t_start
            if elapsed > time_budget:
                partial_reason = partial_reason or f"time_budget_exceeded before tailoring (elapsed {elapsed:.0f}s)"
                log.warning("skipping tailoring: over time budget")
            else:
                _tailor_and_render(top, profile, run_date, gemini_client)

    except KeyboardInterrupt as e:
        partial_reason = partial_reason or f"interrupted: {e}"
        log.warning("pipeline interrupted: %s", e)
    except Exception as e:  # noqa: BLE001
        partial_reason = partial_reason or f"crashed: {type(e).__name__}: {e}"
        log.exception("pipeline crashed: %s", e)
    finally:
        # 6. Reports — always write whatever state we reached.
        stats = RunStats(
            run_date=run_date.isoformat(),
            total_fetched=len(all_jobs),
            fresh_count=len(fresh),
            dedup_skip=len(skipped),
            heuristic_evaluated=len(scored_pairs),
            heuristic_passed=len(passed),
            gemini_scored=sum(1 for sj in scored_jobs if sj.gemini),
            top_n=len(top),
            min_heuristic=min_heur,
            min_final=min_final,
            source_failures=[r.source for r in results if not r.ok],
            duration_s=time.monotonic() - t_start,
            partial_reason=partial_reason,
        )
        try:
            brief_path = write_brief(run_date, results, top, close, stats)
            write_jobs_json(run_date, scored_jobs)
            append_run_log(stats)
        except Exception as e:  # noqa: BLE001
            log.exception("report writing failed: %s", e)

        # 7. Email (best-effort) — send even on partial runs so the user sees
        # the failure.
        if brief_path and not args.dry_run and not args.no_email:
            _maybe_email(brief_path, run_date)

        # Console summary
        print(f"\nJobHunt {run_date.isoformat()} done in {stats.duration_s:.1f}s"
              + (f" (PARTIAL: {partial_reason})" if partial_reason else ""))
        print(f"  fetched={stats.total_fetched} fresh={stats.fresh_count} passed_heuristic={stats.heuristic_passed}")
        print(f"  gemini_scored={stats.gemini_scored} top_n={stats.top_n}")
        if brief_path:
            print(f"  brief: {brief_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

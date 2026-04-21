"""JobHunt entrypoint.

Right now this only wires up sources + dedupe. Scoring, tailoring, rendering,
and reporting will be added in later build steps. The CLI shape is chosen to
be stable across those additions.

Run:
    python -m src.main --dry-run
    python -m src.main --only greenhouse,lever --limit 10
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from src.config import load_search, load_targets
from src.dedupe import SeenStore
from src.models import Job, SourceResult
from src.sources import greenhouse, lever

log = logging.getLogger("jobhunt")


@dataclass
class Registry:
    """Maps source name -> (targets_key_in_targets_yaml, fetch_fn)."""

    fetchers: dict[str, tuple[str, Callable[[list[str], dict[str, Any]], list[Job]]]] = field(default_factory=dict)

    def register(self, name: str, targets_key: str, fn: Callable[[list[str], dict[str, Any]], list[Job]]) -> None:
        self.fetchers[name] = (targets_key, fn)


def default_registry() -> Registry:
    reg = Registry()
    reg.register(greenhouse.NAME, "greenhouse", greenhouse.fetch)
    reg.register(lever.NAME, "lever", lever.fetch)
    return reg


def run_sources(
    registry: Registry,
    targets: dict[str, list[str]],
    search: dict[str, Any],
    only: set[str] | None = None,
) -> list[SourceResult]:
    results: list[SourceResult] = []
    for name, (targets_key, fn) in registry.fetchers.items():
        if only and name not in only:
            continue
        slugs = targets.get(targets_key, [])
        if not slugs:
            results.append(SourceResult(source=name, jobs=[], error="no targets configured"))
            continue
        t0 = time.monotonic()
        try:
            jobs = fn(slugs, search)
            results.append(SourceResult(source=name, jobs=jobs, duration_s=round(time.monotonic() - t0, 2)))
            log.info(json.dumps({"event": "source_done", "source": name, "count": len(jobs)}))
        except Exception as e:  # noqa: BLE001
            results.append(
                SourceResult(source=name, jobs=[], error=str(e), duration_s=round(time.monotonic() - t0, 2))
            )
            log.warning(json.dumps({"event": "source_failed", "source": name, "error": str(e)}))
    return results


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="JobHunt daily pipeline")
    p.add_argument("--dry-run", action="store_true", help="Fetch, dedupe, and print; do not write CVs or emails")
    p.add_argument("--only", type=str, default="", help="Comma-separated source names to run (e.g. greenhouse,lever)")
    p.add_argument("--limit", type=int, default=0, help="Cap total jobs printed per source (0 = no cap)")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
    )

    targets = load_targets()
    search = load_search()
    only = {s.strip() for s in args.only.split(",") if s.strip()} or None

    registry = default_registry()
    results = run_sources(registry, targets, search, only=only)

    total_fetched = sum(len(r.jobs) for r in results)
    print(f"\nFetched {total_fetched} jobs across {len(results)} sources.")
    for r in results:
        status = "ok" if r.ok else f"FAILED: {r.error}"
        print(f"  [{r.source}] {len(r.jobs)} jobs in {r.duration_s}s ({status})")

    all_jobs: list[Job] = [j for r in results for j in r.jobs]
    with SeenStore() as store:
        fresh, skipped = store.partition(all_jobs, within_days=int(search.get("dedupe_skip_days", 14)))
    print(f"Dedupe: {len(fresh)} fresh / {len(skipped)} previously seen.")

    if args.dry_run:
        shown = 0
        for r in results:
            print(f"\n--- {r.source} ---")
            for j in r.jobs:
                if args.limit and shown >= args.limit:
                    break
                print(f"  {j.company} | {j.title} | {j.location or '-'} | remote={j.remote} | {j.apply_url}")
                shown += 1

    print("\nStep 1-4 pipeline complete. Scoring, tailoring, rendering, reporting come next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""SQLite-backed dedup for jobs we've already processed.

Fingerprint = sha256(lower(company) + "||" + lower(title) + "||" + apply_url).

We track the description hash too so we can re-score when a posting changes.
"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from src.models import Job

DEFAULT_DB = Path(__file__).resolve().parent.parent / "db" / "seen.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    fingerprint   TEXT PRIMARY KEY,
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL,
    source        TEXT NOT NULL,
    apply_url     TEXT NOT NULL,
    description_hash TEXT NOT NULL
);
"""


def fingerprint(job: Job) -> str:
    payload = f"{job.company.strip().lower()}||{job.title.strip().lower()}||{job.apply_url.strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def description_hash(description: str) -> str:
    return hashlib.sha256((description or "").encode("utf-8")).hexdigest()


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@contextmanager
def connect(db_path: Path | str = DEFAULT_DB) -> Iterator[sqlite3.Connection]:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


class SeenStore:
    """Thin wrapper. Use `with SeenStore() as store: ...` or pass a conn in."""

    def __init__(self, db_path: Path | str | None = None):
        # Look up DEFAULT_DB at call time so tests can monkeypatch it.
        self._db_path = Path(db_path) if db_path is not None else DEFAULT_DB
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> "SeenStore":
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.executescript(SCHEMA)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self._conn is not None
        if exc_type is None:
            self._conn.commit()
        self._conn.close()
        self._conn = None

    # --- public API ---------------------------------------------------------

    def already_scored_recently(self, job: Job, within_days: int = 14) -> bool:
        """Return True if this fingerprint was seen in the window AND the
        description hasn't changed since. Callers should skip Gemini scoring
        for these.
        """
        assert self._conn is not None
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=within_days)).isoformat()
        fp = fingerprint(job)
        row = self._conn.execute(
            "SELECT last_seen, description_hash FROM seen WHERE fingerprint = ?",
            (fp,),
        ).fetchone()
        if not row:
            return False
        last_seen, stored_hash = row
        if last_seen < cutoff:
            return False
        return stored_hash == description_hash(job.description)

    def record(self, job: Job) -> None:
        """Insert if new; otherwise refresh last_seen + description_hash."""
        assert self._conn is not None
        fp = fingerprint(job)
        now = _utcnow()
        dhash = description_hash(job.description)
        self._conn.execute(
            """
            INSERT INTO seen (fingerprint, first_seen, last_seen, source, apply_url, description_hash)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(fingerprint) DO UPDATE SET
                last_seen = excluded.last_seen,
                description_hash = excluded.description_hash
            """,
            (fp, now, now, job.source, job.apply_url, dhash),
        )

    def partition(self, jobs: list[Job], within_days: int = 14) -> tuple[list[Job], list[Job]]:
        """Split jobs into (fresh, skip_because_seen). Records every job.

        "Fresh" means: never seen before, or last seen outside the window, or
        the description has changed since we last looked.
        """
        fresh: list[Job] = []
        skip: list[Job] = []
        for j in jobs:
            if self.already_scored_recently(j, within_days=within_days):
                skip.append(j)
            else:
                fresh.append(j)
            self.record(j)
        return fresh, skip

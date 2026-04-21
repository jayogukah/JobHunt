"""Tests for the sqlite dedup store."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.dedupe import SeenStore, description_hash, fingerprint
from src.models import Job


def _job(apply_url: str = "https://x.test/abc", description: str = "Do AI things.") -> Job:
    return Job(
        source="greenhouse",
        source_id="1",
        title="AI Engineer",
        company="Example",
        location="Remote",
        remote=True,
        description=description,
        apply_url=apply_url,
    )


def test_fingerprint_is_deterministic():
    assert fingerprint(_job()) == fingerprint(_job())
    assert fingerprint(_job(apply_url="https://x.test/xyz")) != fingerprint(_job())


def test_first_sight_is_fresh(tmp_path: Path):
    db = tmp_path / "seen.sqlite"
    with SeenStore(db) as store:
        fresh, skip = store.partition([_job()])
    assert len(fresh) == 1
    assert skip == []


def test_second_sight_is_deduped(tmp_path: Path):
    db = tmp_path / "seen.sqlite"
    with SeenStore(db) as store:
        store.partition([_job()])
    # Re-open to prove state persists.
    with SeenStore(db) as store:
        fresh, skip = store.partition([_job()])
    assert fresh == []
    assert len(skip) == 1


def test_changed_description_rescores(tmp_path: Path):
    db = tmp_path / "seen.sqlite"
    with SeenStore(db) as store:
        store.partition([_job(description="original")])
    with SeenStore(db) as store:
        fresh, skip = store.partition([_job(description="updated")])
    assert len(fresh) == 1
    assert skip == []


def test_outside_window_rescores(tmp_path: Path):
    import sqlite3

    db = tmp_path / "seen.sqlite"
    j = _job()
    with SeenStore(db) as store:
        store.partition([j])
    # Backdate last_seen to 20 days ago, beyond the default window of 14.
    old = (datetime.now(tz=timezone.utc) - timedelta(days=20)).isoformat()
    con = sqlite3.connect(str(db))
    con.execute("UPDATE seen SET last_seen = ? WHERE fingerprint = ?", (old, fingerprint(j)))
    con.commit()
    con.close()

    with SeenStore(db) as store:
        fresh, skip = store.partition([j])
    assert len(fresh) == 1
    assert skip == []


def test_description_hash_stable():
    assert description_hash("x") == description_hash("x")
    assert description_hash("x") != description_hash("y")

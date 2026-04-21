"""Smoke tests for the normalize helpers."""

from datetime import datetime, timezone

from src.normalize import clean_html, detect_remote, parse_ts, short_location


def test_clean_html_strips_tags_and_entities():
    html_in = "<p>Hello &amp; <b>world</b></p>\n\n\n<ul><li>one</li><li>two</li></ul>"
    out = clean_html(html_in)
    assert "<" not in out and ">" not in out
    assert "&amp;" not in out
    assert "Hello & world" in out
    assert "one" in out and "two" in out
    # collapse 3+ newlines to 2
    assert "\n\n\n" not in out


def test_clean_html_handles_empty():
    assert clean_html(None) == ""
    assert clean_html("") == ""


def test_parse_ts_iso_and_epoch():
    dt = parse_ts("2025-04-01T12:34:56Z")
    assert dt is not None and dt.tzinfo is not None
    assert parse_ts(None) is None
    assert parse_ts("") is None
    # millisecond epoch
    dt_ms = parse_ts(1_700_000_000_000)
    assert isinstance(dt_ms, datetime) and dt_ms.tzinfo == timezone.utc
    # naive strings get tagged as UTC
    naive = parse_ts("2025-04-01 12:34:56")
    assert naive is not None and naive.tzinfo is not None


def test_detect_remote():
    assert detect_remote("Remote - EU", "") is True
    assert detect_remote("London, UK", "This is an on-site role.") is False
    assert detect_remote("London, UK", "Standard office job.") is None


def test_short_location():
    assert short_location([None, " ", "London", "UK"]) == "London, UK"
    assert short_location([None, ""]) is None

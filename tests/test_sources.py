"""Smoke tests for Greenhouse and Lever source parsers.

We do not hit the network. We feed the parsers a fixture payload shaped like
the real API response and verify the Job objects come out sane.
"""

from __future__ import annotations

from src.sources import greenhouse, lever


GREENHOUSE_FIXTURE = {
    "jobs": [
        {
            "id": 4567,
            "title": "Senior AI Automation Engineer",
            "content": "<p>Build <b>agentic</b> systems.</p><ul><li>Python</li><li>LLMs</li></ul>",
            "absolute_url": "https://boards.greenhouse.io/example/jobs/4567",
            "updated_at": "2025-04-10T09:00:00Z",
            "first_published": "2025-04-01T09:00:00Z",
            "location": {"name": "Remote - EU"},
            "offices": [{"name": "London"}],
            "departments": [{"name": "Engineering"}],
            "company_name": "Example Co",
            "requisition_id": "R-123",
        },
        # A deliberately broken record to make sure the parser skips it
        # rather than aborting the whole board.
        {"id": None, "title": None},
    ]
}


def test_greenhouse_parse(monkeypatch):
    monkeypatch.setattr(greenhouse, "http_get_json", lambda url, params=None: GREENHOUSE_FIXTURE)
    jobs = greenhouse.fetch_board("example")
    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "greenhouse"
    assert j.source_id == "4567"
    assert j.title == "Senior AI Automation Engineer"
    assert j.company == "Example Co"
    assert j.location and "Remote" in j.location
    assert j.remote is True
    assert "Python" in j.description and "<" not in j.description
    assert j.apply_url.endswith("/4567")
    assert j.posted_at is not None
    assert j.raw["board_token"] == "example"


LEVER_FIXTURE = [
    {
        "id": "abc-123",
        "text": "LLM Engineer",
        "hostedUrl": "https://jobs.lever.co/example/abc-123",
        "applyUrl": "https://jobs.lever.co/example/abc-123/apply",
        "createdAt": 1_700_000_000_000,
        "categories": {
            "location": "Berlin, Germany",
            "commitment": "Full-time",
            "team": "Applied AI",
            "department": "Engineering",
        },
        "workplaceType": "hybrid",
        "descriptionPlain": "We build retrieval systems.",
        "lists": [
            {"text": "What you'll do", "content": "<ul><li>Own pipelines</li><li>Ship fast</li></ul>"},
            {"text": "Requirements", "content": "<ul><li>Python</li><li>SQL</li></ul>"},
        ],
        "additionalPlain": "Onsite-friendly, hybrid schedule.",
    },
    # Broken record: no id/text.
    {"id": None},
]


def test_lever_parse(monkeypatch):
    monkeypatch.setattr(lever, "http_get_json", lambda url, params=None: LEVER_FIXTURE)
    jobs = lever.fetch_company("example")
    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "lever"
    assert j.source_id == "abc-123"
    assert j.title == "LLM Engineer"
    assert j.company == "example"
    assert j.location and "Berlin" in j.location
    assert "Own pipelines" in j.description and "Ship fast" in j.description
    assert "<" not in j.description
    assert j.apply_url.startswith("https://jobs.lever.co/")
    assert j.posted_at is not None
    assert j.raw["team"] == "Applied AI"


def test_lever_empty_response(monkeypatch):
    monkeypatch.setattr(lever, "http_get_json", lambda url, params=None: {})
    assert lever.fetch_company("example") == []

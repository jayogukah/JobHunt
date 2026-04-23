"""Tests for the heuristic prefilter."""

from src.models import Job
from src.score import score


def _job(title: str, description: str = "", location: str | None = "Remote", remote: bool | None = True) -> Job:
    return Job(
        source="test",
        source_id="1",
        title=title,
        company="Example Co",
        location=location,
        remote=remote,
        description=description,
        apply_url="https://example.com/jobs/1",
    )


SEARCH = {
    "keywords": ["AI automation engineer", "RPA engineer", "LLM engineer"],
    "locations": ["United Kingdom", "Germany", "Remote"],
    "remote_ok": True,
    "visa_sponsorship_required": True,
    "exclude_keywords": ["intern", "entry level"],
}
CTX = {"current_country": "Nigeria", "needs_sponsorship": True, "seniority": "senior"}


def test_strong_match_scores_high():
    j = _job(
        "Senior AI Automation Engineer",
        description="We offer visa sponsorship and relocation support for the right candidate. Python, LLMs.",
        location="Remote - EU",
        remote=True,
    )
    s = score(j, SEARCH, CTX)
    assert s.score > 0.8
    assert s.location_match is True
    assert s.sponsorship_signal == "positive"
    assert s.seniority_match is True
    assert s.keyword_hits  # at least one hit


def test_excluded_keyword_zeroes_out():
    j = _job("Automation Engineer Internship", description="Great entry level role.")
    s = score(j, SEARCH, CTX)
    assert s.score == 0.0
    assert s.excluded_by in {"intern", "entry level"}


def test_negative_sponsorship_penalizes():
    j = _job(
        "Senior LLM Engineer",
        description="Must have the right to work in the United States. No sponsorship offered.",
        location="New York, NY",
        remote=False,
    )
    s = score(j, SEARCH, CTX)
    assert s.sponsorship_signal == "negative"
    # Not in Nigeria, so sponsorship score is 0 and total drops accordingly.
    assert s.score < 0.7


def test_seniority_mismatch_penalized():
    j = _job(
        "Junior Automation Engineer",
        description="We sponsor visas. Python.",
        location="London, UK",
        remote=False,
    )
    s = score(j, SEARCH, CTX)
    assert s.seniority_match is False
    # Seniority score floors at 0.1 for junior when candidate is senior.
    # Total stays below the strong-match threshold.
    assert s.score < 0.7


def test_unknown_sponsorship_neutral():
    j = _job(
        "Senior Automation Engineer",
        description="Come build with us. Python, Power Automate.",
        location="Berlin, Germany",
        remote=False,
    )
    s = score(j, SEARCH, CTX)
    assert s.sponsorship_signal == "unknown"
    # Still passes the default min_heuristic_score of 0.4.
    assert s.score >= 0.4

"""Tests for the Gemini deep-score pass. We never hit the network — the
LLM client is stubbed with a canned payload.
"""

from __future__ import annotations

from src.models import Job
from src.score import score_job_llm, voice_scrub, summarize_profile


class _StubClient:
    def __init__(self, payload: dict):
        self.payload = payload
        self.last_prompt: str | None = None
        self.last_system: str | None = None

    def generate_json(self, prompt: str, *, system: str | None = None) -> dict:
        self.last_prompt = prompt
        self.last_system = system
        return self.payload


JOB = Job(
    source="greenhouse",
    source_id="1",
    title="Senior AI Automation Engineer",
    company="Example Co",
    location="Remote - EU",
    remote=True,
    description="We sponsor visas. Python, Gemini API, UiPath.",
    apply_url="https://example.com/jobs/1",
)

PROFILE = {
    "identity": {"name": "Praise Ogukah"},
    "context": {"current_country": "Nigeria", "needs_sponsorship": True, "seniority": "senior"},
    "summary": "Automation developer with 6 years building RPA and AI systems.",
    "competencies": ["UiPath", "Python", "Gemini API"],
    "experience": [
        {
            "company": "KPMG West Africa",
            "role": "Senior Automation Developer",
            "start": "2022-05",
            "end": "present",
            "bullets": ["Built Gemini pipelines for KYC."],
        }
    ],
    "certifications": [
        {"name": "UiPath UiARD", "status": "active"},
        {"name": "Azure AI-102", "status": "in-progress"},
    ],
}


def test_score_job_happy_path():
    client = _StubClient({
        "fit_score": 0.85,
        "sponsorship_likely": "yes",
        "strengths": ["UiPath match", "Gemini API match"],
        "gaps": ["No direct UK experience"],
        "red_flags": [],
        "why_apply": "Strong toolchain overlap. Sponsorship is explicit. Worth applying.",
        "why_skip": "",
    })
    result = score_job_llm(client, JOB, PROFILE)
    assert result.fit_score == 0.85
    assert result.sponsorship_likely == "yes"
    assert result.strengths and result.gaps
    assert "Strong toolchain" in result.why_apply
    # Profile snippets should appear in the prompt the stub saw.
    assert "Praise Ogukah" in client.last_prompt
    assert "UiPath" in client.last_prompt


def test_score_job_clamps_score_to_unit_interval():
    client = _StubClient({"fit_score": 1.7, "why_apply": "ok"})
    assert score_job_llm(client, JOB, PROFILE).fit_score == 1.0
    client2 = _StubClient({"fit_score": -0.3, "why_apply": "nope"})
    assert score_job_llm(client2, JOB, PROFILE).fit_score == 0.0


def test_score_job_normalises_sponsorship():
    client = _StubClient({"fit_score": 0.5, "sponsorship_likely": "likely", "why_apply": "x"})
    assert score_job_llm(client, JOB, PROFILE).sponsorship_likely == "yes"
    client2 = _StubClient({"fit_score": 0.5, "sponsorship_likely": "nope", "why_apply": "x"})
    assert score_job_llm(client2, JOB, PROFILE).sponsorship_likely == "unclear"


def test_voice_scrub_replaces_em_dash_and_banned_words():
    text = "Leveraged Python — spearheaded migrations."
    out = voice_scrub(text)
    assert "—" not in out
    assert "Leveraged" not in out and "spearheaded" not in out
    assert "Used Python" in out or "Used python" in out.lower()


def test_voice_scrub_handles_empty():
    assert voice_scrub("") == ""
    assert voice_scrub(None) == ""  # type: ignore[arg-type]


def test_summarize_profile_stays_compact():
    text = summarize_profile(PROFILE)
    # sanity: reasonable size, includes core signals
    assert len(text) < 4000
    assert "Praise Ogukah" in text
    assert "UiPath" in text
    assert "senior" in text.lower()

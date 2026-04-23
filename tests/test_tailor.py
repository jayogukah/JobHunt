"""Tests for the tailoring pass."""

from __future__ import annotations

from src.models import Job
from src.tailor import tailor_cv


class _StubClient:
    def __init__(self, payload: dict):
        self.payload = payload
        self.last_prompt: str | None = None

    def generate_json(self, prompt: str, *, system: str | None = None) -> dict:
        self.last_prompt = prompt
        return self.payload


JOB = Job(
    source="greenhouse",
    source_id="1",
    title="Senior AI Automation Engineer",
    company="Example Co",
    location="Remote - EU",
    remote=True,
    description="UiPath, Power Automate, Gemini API. We sponsor visas.",
    apply_url="https://example.com/jobs/1",
)

PROFILE = {
    "summary": "Automation developer.",
    "competencies": ["UiPath", "Python"],
    "experience": [
        {
            "company": "KPMG West Africa",
            "role": "Senior Automation Developer",
            "start": "2022-05",
            "end": "present",
            "bullets": ["Built automations."],
        },
        {
            "company": "Sterling Bank PLC",
            "role": "RPA Developer",
            "start": "2020-03",
            "end": "2022-04",
            "bullets": ["Wrote UiPath bots."],
        },
    ],
    "education": [],
    "certifications": [{"name": "UiARD", "status": "active"}],
    "projects": [],
}


def test_tailor_cv_happy_path():
    payload = {
        "summary": "Automation developer with UiPath and Gemini API experience.",
        "competencies_ordered": ["UiPath", "Gemini API", "Python"],
        "experience": [
            {
                "company": "KPMG West Africa",
                "role": "Senior Automation Developer",
                "bullets": ["UiPath bots for KYC, processing 1000+ records.", "Gemini API for loan underwriting."],
            },
            {
                "company": "Sterling Bank PLC",
                "role": "RPA Developer",
                "bullets": ["UiPath handling 500,000 weekly records."],
            },
        ],
        "keywords_added": ["UiPath", "Gemini API"],
    }
    result = tailor_cv(_StubClient(payload), JOB, PROFILE)
    assert len(result.experience) == 2
    assert result.experience[0].company == "KPMG West Africa"
    assert result.summary.startswith("Automation developer")
    assert "UiPath" in result.competencies_ordered


def test_tailor_cv_drops_fabricated_employer():
    payload = {
        "summary": "x",
        "competencies_ordered": [],
        "experience": [
            {"company": "KPMG West Africa", "role": "Senior Automation Developer", "bullets": ["ok"]},
            {"company": "Google", "role": "Staff Engineer", "bullets": ["fake"]},
        ],
        "keywords_added": [],
    }
    result = tailor_cv(_StubClient(payload), JOB, PROFILE)
    companies = {e.company for e in result.experience}
    assert "Google" not in companies
    assert "KPMG West Africa" in companies


def test_tailor_cv_trims_oversized_bullets():
    long_bullet = " ".join(["word"] * 30)
    payload = {
        "summary": "x",
        "competencies_ordered": [],
        "experience": [
            {"company": "KPMG West Africa", "role": "Senior Automation Developer", "bullets": [long_bullet]},
        ],
        "keywords_added": [],
    }
    result = tailor_cv(_StubClient(payload), JOB, PROFILE)
    bullet = result.experience[0].bullets[0]
    assert len(bullet.split()) <= 26  # 25 words + trailing period


def test_tailor_cv_scrubs_banned_phrases():
    payload = {
        "summary": "Leveraged Gemini API — spearheaded automation.",
        "competencies_ordered": [],
        "experience": [],
        "keywords_added": [],
    }
    result = tailor_cv(_StubClient(payload), JOB, PROFILE)
    assert "—" not in result.summary
    assert "Leveraged" not in result.summary
    assert "spearheaded" not in result.summary

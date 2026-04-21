"""Pydantic schemas shared across the pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Job(BaseModel):
    """Unified job record produced by every source after normalization."""

    model_config = ConfigDict(extra="ignore")

    source: str
    source_id: str
    title: str
    company: str
    location: str | None = None
    remote: bool | None = None
    description: str
    apply_url: str
    posted_at: datetime | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class HeuristicScore(BaseModel):
    score: float
    keyword_hits: list[str] = Field(default_factory=list)
    location_match: bool = False
    sponsorship_signal: Literal["positive", "negative", "unknown"] = "unknown"
    seniority_match: bool = False
    excluded_by: str | None = None


class GeminiScore(BaseModel):
    fit_score: float
    sponsorship_likely: Literal["yes", "no", "unclear"] = "unclear"
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    why_apply: str = ""
    why_skip: str = ""


class ScoredJob(BaseModel):
    job: Job
    heuristic: HeuristicScore
    gemini: GeminiScore | None = None
    tailored_cv_path: str | None = None

    @property
    def final_score(self) -> float:
        return self.gemini.fit_score if self.gemini else self.heuristic.score


class TailoredExperience(BaseModel):
    company: str
    role: str
    bullets: list[str] = Field(default_factory=list)


class TailoredCV(BaseModel):
    summary: str
    competencies_ordered: list[str] = Field(default_factory=list)
    experience: list[TailoredExperience] = Field(default_factory=list)
    keywords_added: list[str] = Field(default_factory=list)


class SourceResult(BaseModel):
    """Per-source execution summary for the daily brief."""

    source: str
    jobs: list[Job] = Field(default_factory=list)
    error: str | None = None
    duration_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.error is None

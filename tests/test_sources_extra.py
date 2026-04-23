"""Smoke tests for the remaining sources. All mock http_get_* at the module
boundary so we never touch the network.
"""

from __future__ import annotations

from src.sources import adzuna, arbeitnow, ashby, hn_whoishiring, personio, remotive, workable


# ---- Ashby -----------------------------------------------------------------

ASHBY_FIXTURE = {
    "jobs": [
        {
            "id": "ashby-1",
            "title": "Staff AI Engineer",
            "teamName": "Applied AI",
            "locationName": "Remote (Global)",
            "isRemote": True,
            "descriptionHtml": "<p>Work on <b>LLM</b> systems.</p>",
            "jobUrl": "https://jobs.ashbyhq.com/example/ashby-1",
            "publishedAt": "2025-04-15T10:00:00Z",
            "employmentType": "FullTime",
            "departmentName": "Engineering",
        },
        {"id": None, "title": None, "jobUrl": None},
    ]
}


def test_ashby_parse(monkeypatch):
    monkeypatch.setattr(ashby, "http_get_json", lambda url, params=None: ASHBY_FIXTURE)
    jobs = ashby.fetch_board("example")
    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "ashby"
    assert j.title == "Staff AI Engineer"
    assert j.remote is True
    assert "LLM" in j.description and "<" not in j.description
    assert j.apply_url.endswith("/ashby-1")


# ---- Workable --------------------------------------------------------------

WORKABLE_FIXTURE = {
    "jobs": [
        {
            "id": "wk-1",
            "shortcode": "WK01",
            "title": "Senior Automation Engineer",
            "description": "<p>Python + RPA.</p>",
            "application_url": "https://apply.workable.com/example/j/WK01/",
            "url": "https://apply.workable.com/example/j/WK01/",
            "location": {"city": "Berlin", "country": "Germany", "workplace": "hybrid"},
            "company_name": "Example GmbH",
            "published_on": "2025-04-10",
            "department": "Engineering",
        },
        {"shortcode": None, "title": None},
    ]
}


def test_workable_parse(monkeypatch):
    monkeypatch.setattr(workable, "http_get_json", lambda url, params=None: WORKABLE_FIXTURE)
    jobs = workable.fetch_board("example")
    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "workable"
    assert j.location and "Berlin" in j.location
    assert "<" not in j.description
    assert j.company == "Example GmbH"


# ---- Personio --------------------------------------------------------------

PERSONIO_XML = """
<workzag-jobs>
  <position>
    <id>101</id>
    <name>Senior Automation Developer</name>
    <office>Munich</office>
    <department>Engineering</department>
    <subcompany>ExampleCo</subcompany>
    <employmentType>full-time</employmentType>
    <schedule>full-time</schedule>
    <createdAt>2025-04-01T09:00:00+00:00</createdAt>
    <url>https://example.jobs.personio.com/job/101</url>
    <jobDescriptions>
      <jobDescription>
        <name>Your role</name>
        <value><![CDATA[<p>Build <b>automation</b> systems.</p>]]></value>
      </jobDescription>
      <jobDescription>
        <name>Your profile</name>
        <value><![CDATA[<ul><li>Python</li><li>UiPath</li></ul>]]></value>
      </jobDescription>
    </jobDescriptions>
  </position>
  <position>
    <id></id>
    <name></name>
    <url></url>
  </position>
</workzag-jobs>
"""


def test_personio_parse(monkeypatch):
    monkeypatch.setattr(personio, "http_get_text", lambda url, params=None: PERSONIO_XML)
    jobs = personio.fetch_board("example")
    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "personio"
    assert j.title == "Senior Automation Developer"
    assert "Python" in j.description and "UiPath" in j.description
    assert "Munich" in (j.location or "")
    assert j.apply_url.endswith("/job/101")


# ---- Remotive --------------------------------------------------------------

REMOTIVE_FIXTURE = {
    "jobs": [
        {
            "id": 99,
            "title": "AI Automation Engineer",
            "company_name": "RemoteCo",
            "candidate_required_location": "EMEA",
            "publication_date": "2025-04-18T00:00:00",
            "description": "<p>Python + Gemini.</p>",
            "url": "https://remotive.com/remote-jobs/99",
            "salary": "$120,000 - $160,000",
        },
        {"id": None, "url": None, "title": None},
    ]
}


def test_remotive_parse(monkeypatch):
    monkeypatch.setattr(remotive, "http_get_json", lambda url, params=None: REMOTIVE_FIXTURE)
    jobs = remotive.fetch_keyword("AI")
    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "remotive"
    assert j.remote is True
    assert j.salary_min == 120000.0
    assert j.salary_max == 160000.0


# ---- Arbeitnow -------------------------------------------------------------

ARBEITNOW_FIXTURE = {
    "data": [
        {
            "slug": "senior-ai-eng",
            "title": "Senior AI Engineer",
            "company_name": "EU Co",
            "location": "Berlin",
            "description": "<p>Python, LLMs.</p>",
            "url": "https://www.arbeitnow.com/jobs/senior-ai-eng",
            "created_at": 1_714_000_000,
            "remote": True,
            "visa_sponsorship": True,
        },
        {"slug": None, "title": None, "url": None},
    ]
}


def test_arbeitnow_parse(monkeypatch):
    monkeypatch.setattr(arbeitnow, "http_get_json", lambda url, params=None: ARBEITNOW_FIXTURE)
    jobs = arbeitnow.fetch_all()
    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "arbeitnow"
    assert j.remote is True
    assert "Berlin" in (j.location or "")
    assert j.raw.get("visa_sponsorship") is True


# ---- Adzuna ----------------------------------------------------------------

ADZUNA_FIXTURE = {
    "results": [
        {
            "id": "adz-1",
            "title": "RPA Engineer",
            "description": "Work on UiPath and Python automations.",
            "redirect_url": "https://www.adzuna.co.uk/jobs/1",
            "created": "2025-04-15T12:00:00Z",
            "company": {"display_name": "UK Bank"},
            "location": {"area": ["UK", "London"]},
            "salary_min": 70000,
            "salary_max": 95000,
            "category": {"label": "IT"},
            "contract_type": "permanent",
        }
    ]
}


def test_adzuna_parse(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "x")
    monkeypatch.setenv("ADZUNA_APP_KEY", "y")
    monkeypatch.setattr(adzuna, "http_get_json", lambda url, params=None: ADZUNA_FIXTURE)
    jobs = adzuna.fetch_country_keyword("gb", "RPA engineer")
    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "adzuna"
    assert j.salary_min == 70000
    assert j.location and "London" in j.location
    assert j.company == "UK Bank"


def test_adzuna_missing_keys_raises(monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    try:
        adzuna.fetch_country_keyword("gb", "x")
    except RuntimeError as e:
        assert "ADZUNA_APP_ID" in str(e)
    else:
        raise AssertionError("expected RuntimeError")


# ---- HN Who is hiring ------------------------------------------------------

HN_STORY_FIXTURE = {
    "hits": [
        {"objectID": "40000000", "title": "Ask HN: Who is hiring? (April 2025)", "created_at_i": 1_714_000_000},
        {"objectID": "39999999", "title": "Ask HN: Who is hiring? (March 2025)", "created_at_i": 1_711_000_000},
    ]
}

HN_COMMENTS_FIXTURE = {
    "hits": [
        {
            "objectID": "40001234",
            "comment_text": "<p>Stripe (YC S10) | Remote, EU | Senior AI Engineer | Python, LLMs.</p>",
            "created_at": "2025-04-02T12:00:00Z",
            "created_at_i": 1_714_050_000,
            "points": 1,
        },
        {"objectID": None, "comment_text": ""},
    ]
}


def test_hn_parse_and_extract(monkeypatch):
    responses = [HN_STORY_FIXTURE, HN_COMMENTS_FIXTURE]

    def fake(url, params=None):
        return responses.pop(0)

    monkeypatch.setattr(hn_whoishiring, "http_get_json", fake)
    jobs = hn_whoishiring.fetch([], {"keywords": ["AI"]})
    assert len(jobs) == 1
    j = jobs[0]
    assert j.source == "hn_whoishiring"
    assert j.company == "Stripe"
    assert j.location and "Remote" in j.location
    assert j.apply_url.startswith("https://news.ycombinator.com/item?id=")
    assert j.remote is True


def test_hn_no_story_returns_empty(monkeypatch):
    monkeypatch.setattr(hn_whoishiring, "http_get_json", lambda url, params=None: {"hits": []})
    assert hn_whoishiring.fetch([], {"keywords": ["AI"]}) == []

"""Shared fixtures for O*NET client tests.

Uses inheritance-based stubs (Harrison style) — a fake httpx transport
that returns canned JSON responses without hitting the real API.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from onet.client import OnetClient

# ---------------------------------------------------------------------------
# Canned API responses — minimal but structurally accurate
# ---------------------------------------------------------------------------

SEARCH_RESPONSE = {
    "start": 1,
    "end": 2,
    "total": 2,
    "occupation": [
        {
            "href": "https://api-v2.onetcenter.org/online/occupations/25-2021.00/",
            "code": "25-2021.00",
            "title": "Elementary School Teachers, Except Special Education",
            "tags": {},
        },
        {
            "href": "https://api-v2.onetcenter.org/online/occupations/25-2022.00/",
            "code": "25-2022.00",
            "title": "Middle School Teachers",
            "tags": {},
        },
    ],
}

OCCUPATION_RESPONSE = {
    "code": "25-2021.00",
    "title": "Elementary School Teachers, Except Special Education",
    "description": "Teach academic and social skills to students at the elementary school level.",
    "sample_of_reported_titles": ["Teacher", "Elementary Teacher"],
}

KNOWLEDGE_RESPONSE = {
    "start": 1,
    "end": 2,
    "total": 2,
    "element": [
        {
            "id": "2.C.7.a",
            "name": "English Language",
            "description": "Knowledge of English.",
            "importance": 97,
        },
        {
            "id": "2.C.6",
            "name": "Education and Training",
            "description": "Knowledge of education principles.",
            "importance": 96,
        },
    ],
}

SKILLS_RESPONSE = {
    "start": 1,
    "end": 2,
    "total": 2,
    "element": [
        {
            "id": "2.A.1.a",
            "name": "Reading Comprehension",
            "description": "Understanding written text.",
            "importance": 72,
        },
        {
            "id": "2.A.1.d",
            "name": "Speaking",
            "description": "Talking to others.",
            "importance": 78,
        },
    ],
}

ABILITIES_RESPONSE = {
    "start": 1,
    "end": 1,
    "total": 1,
    "element": [
        {
            "id": "1.A.1.a.1",
            "name": "Oral Comprehension",
            "description": "Listening.",
            "importance": 75,
        },
    ],
}

WORK_STYLES_RESPONSE = {
    "start": 1,
    "end": 1,
    "total": 1,
    "element": [
        {"id": "1.C.1", "name": "Dependability", "description": "Reliable.", "importance": 88},
    ],
}

INTERESTS_RESPONSE = {
    "start": 1,
    "end": 3,
    "total": 3,
    "element": [
        {
            "id": "1.B.1.d",
            "name": "Social",
            "description": "Helping others.",
            "occupational_interest": 100,
        },
        {
            "id": "1.B.1.c",
            "name": "Artistic",
            "description": "Creating things.",
            "occupational_interest": 48,
        },
        {
            "id": "1.B.1.b",
            "name": "Investigative",
            "description": "Researching.",
            "occupational_interest": 39,
        },
    ],
}

TASKS_RESPONSE = {
    "start": 1,
    "end": 2,
    "total": 2,
    "task": [
        {
            "id": "6744",
            "title": "Establish rules for behavior.",
            "importance": 88,
            "category": "Core",
        },
        {
            "id": "6748",
            "title": "Prepare materials for class.",
            "importance": 85,
            "category": "Core",
        },
    ],
}

WORK_ACTIVITIES_RESPONSE = {
    "start": 1,
    "end": 1,
    "total": 1,
    "element": [
        {
            "id": "4.A.1.a.1",
            "name": "Getting Information",
            "description": "Observing.",
            "importance": 80,
        },
    ],
}

WORK_CONTEXT_RESPONSE = {
    "start": 1,
    "end": 1,
    "total": 1,
    "element": [
        {
            "id": "4.C.1.a.2.a",
            "name": "Indoors, Environmentally Controlled",
            "description": "Office.",
            "category": "Physical",
            "score": 95,
        },
    ],
}

DETAILED_WORK_ACTIVITIES_RESPONSE = {
    "start": 1,
    "end": 1,
    "total": 1,
    "activity": [
        {"id": "4.A.2.b.2.I15.D08", "title": "Develop educational programs."},
    ],
}

# Captured shape: no pagination block at all, and `code` is an int ordinal.
EDUCATION_RESPONSE = {
    "response": [
        {"code": 7, "title": "Bachelor's degree", "percentage_of_respondents": 78},
        {"code": 8, "title": "Master's degree", "percentage_of_respondents": 22},
    ],
}

# Captured from GET /online/occupations/25-2021.00/details/job_zone.
# `code` is the zone number (1-5), NOT the SOC code, and the experience field
# is named `related_experience` — do not hand-edit this shape.
JOB_ZONE_RESPONSE = {
    "code": 4,
    "title": "Job Zone Four: Considerable Preparation Needed",
    "education": (
        "Most of these occupations require a four-year bachelor's degree, but some do not."
    ),
    "related_experience": (
        "A considerable amount of work-related skill, knowledge, or experience is needed "
        "for these occupations."
    ),
    "job_training": (
        "Employees in these occupations usually need several years of work-related "
        "experience, on-the-job training, and/or vocational training."
    ),
    "job_zone_examples": (
        "Many of these occupations involve coordinating, supervising, managing, or training others."
    ),
    "svp_range": "(7.0 to < 8.0)",
}

HOT_TECHNOLOGY_RESPONSE = {
    "start": 1,
    "end": 1,
    "total": 1,
    "example": [
        {
            "title": "Google Classroom",
            "hot_technology": True,
            "in_demand": True,
            "percentage": 25.0,
        },
    ],
}

# Captured shape: the data key is `category` (NOT `element`), category codes
# are UNSPSC ints, and there is a sibling `hot_technology` pointer object.
# There is no `example_more` list and no `in_demand` flag.
TECHNOLOGY_SKILLS_RESPONSE = {
    "start": 1,
    "end": 1,
    "total": 1,
    "hot_technology": {
        "total": 7,
        "href": "https://api-v2.onetcenter.org/online/occupations/25-2021.00/hot_technology",
    },
    "category": [
        {
            "code": 43233501,
            "related": "https://api-v2.onetcenter.org/online/occupations/25-2021.00/related/technology_skills/43233501",
            "title": "Computer based training software",
            "example": [
                {"title": "Google Classroom", "href": "https://example.invalid/gc"},
                {
                    "title": "Nearpod",
                    "href": "https://example.invalid/np",
                    "hot_technology": True,
                },
            ],
        },
    ],
}

RELATED_OCCUPATIONS_RESPONSE = {
    "start": 1,
    "end": 1,
    "total": 1,
    "occupation": [
        {
            "href": "https://api-v2.onetcenter.org/online/occupations/25-2022.00/",
            "code": "25-2022.00",
            "title": "Middle School Teachers",
        },
    ],
}

# Captured from GET /database — a top-level ARRAY, not an object, and the
# identifier key is `table_id`. Do not hand-edit this shape.
TABLES_RESPONSE = [
    {
        "info": "https://api-v2.onetcenter.org/database/info/essential_skills",
        "rows": "https://api-v2.onetcenter.org/database/rows/essential_skills",
        "table_id": "essential_skills",
        "title": "Essential Skills",
        "description": "Provide essential skills ratings.",
    },
    {
        "info": "https://api-v2.onetcenter.org/database/info/occupation_data",
        "rows": "https://api-v2.onetcenter.org/database/rows/occupation_data",
        "table_id": "occupation_data",
        "title": "Occupation Data",
        "description": "Provide O*NET-SOC codes, titles, and descriptions.",
    },
]

# Captured from GET /database/info/essential_skills. Valid table ids are
# snake_case (`essential_skills`), never display titles like "Skills".
TABLE_INFO_RESPONSE = {
    "table_id": "essential_skills",
    "title": "Essential Skills",
    "description": "Provide essential skills ratings.",
    "rows": "https://api-v2.onetcenter.org/database/rows/essential_skills",
    "data_dictionary": "https://onetcenter.org/dictionary/api/essential_skills",
    "download": {"excel": "https://example.invalid/x.xlsx"},
    "column": [
        {
            "column_id": "O*NET-SOC Code",
            "title": "O*NET-SOC Code",
            "type": "varchar",
            "description": "SOC code",
            "optional": False,
        },
        {
            "column_id": "Element Name",
            "title": "Element Name",
            "type": "varchar",
            "description": "Skill name",
            "optional": False,
        },
        {
            "column_id": "Scale ID",
            "title": "Scale ID",
            "type": "varchar",
            "description": "Importance or Level",
            "optional": False,
        },
        {
            "column_id": "Data Value",
            "title": "Data Value",
            "type": "float",
            "description": "Score",
            "optional": False,
        },
    ],
}

TABLE_ROWS_RESPONSE = {
    "start": 1,
    "end": 2,
    "total": 2,
    "row": [
        {
            "o_net_soc_code": "25-2021.00",
            "element_name": "Reading Comprehension",
            "scale_id": "IM",
            "data_value": 4.12,
        },
        {
            "o_net_soc_code": "25-2021.00",
            "element_name": "Speaking",
            "scale_id": "IM",
            "data_value": 4.25,
        },
    ],
}

# Captured from GET /online/crosswalks/military?keyword=infantry&start=1&end=2.
# The envelope key is "match", and each match nests its civilian O*NET-SOC
# hits under "occupation" — do not hand-edit this shape.
CROSSWALK_MILITARY_RESPONSE = {
    "start": 1,
    "end": 2,
    "total": 13,
    "next": "https://api-v2.onetcenter.org/online/crosswalks/military?keyword=infantry&start=3&end=4",
    "match": [
        {
            "code": "00R",
            "title": "Command Sergeant Major (CSM) Infantry/Armor Immaterial (Army - Enlisted)",
            "occupation": [
                {
                    "href": "https://api-v2.onetcenter.org/online/occupations/11-3121.00/",
                    "code": "11-3121.00",
                    "title": "Human Resources Managers",
                    "tags": {"bright_outlook": True},
                }
            ],
        },
        {
            "code": "0301",
            "title": "Basic Infantry Officer (Marine Corps - Commissioned Officer only)",
            "occupation": [
                {
                    "href": "https://api-v2.onetcenter.org/online/occupations/55-1016.00/",
                    "code": "55-1016.00",
                    "title": "Infantry Officers",
                    "tags": {},
                }
            ],
        },
    ],
}

# Captured shape: the envelope carries the source occupation's own
# code/title/description alongside the mapped `occupation` list.
TAXONOMY_MAP_RESPONSE = {
    "code": "25-2021.00",
    "title": "Elementary School Teachers, Except Special Education",
    "description": "Teach academic and social skills to students.",
    "occupation": [
        {"code": "25-2021.00", "title": "Elementary School Teachers"},
    ],
}

PROFILER_QUESTIONS_RESPONSE = {
    "start": 1,
    "end": 4,
    "total": 4,
    "answer_option": [
        {"value": 1, "name": "Strongly Dislike"},
        {"value": 2, "name": "Dislike"},
        {"value": 3, "name": "Unsure"},
        {"value": 4, "name": "Like"},
        {"value": 5, "name": "Strongly Like"},
    ],
    "question": [
        {"index": 1, "area": "realistic", "text": "Build kitchen cabinets"},
        {"index": 2, "area": "realistic", "text": "Lay brick or tile"},
        {"index": 3, "area": "investigative", "text": "Develop a new medicine"},
        {"index": 4, "area": "investigative", "text": "Study ways to reduce water pollution"},
    ],
}

PROFILER_RESULTS_RESPONSE = {
    "result": [
        {"code": "realistic", "title": "Realistic", "description": "Hands-on work.", "score": 10},
        {
            "code": "investigative",
            "title": "Investigative",
            "description": "Ideas and thinking.",
            "score": 30,
        },
        {"code": "artistic", "title": "Artistic", "description": "Creative work.", "score": 30},
        {"code": "social", "title": "Social", "description": "Helping others.", "score": 40},
        {
            "code": "enterprising",
            "title": "Enterprising",
            "description": "Business projects.",
            "score": 10,
        },
        {
            "code": "conventional",
            "title": "Conventional",
            "description": "Set procedures.",
            "score": 10,
        },
    ],
}

PROFILER_CAREERS_RESPONSE = {
    "start": 1,
    "end": 3,
    "total": 3,
    "career": [
        {"code": "25-2021.00", "title": "Elementary School Teachers", "fit": "Best", "href": ""},
        {"code": "21-1014.00", "title": "Mental Health Counselors", "fit": "Best", "href": ""},
        {"code": "25-3011.00", "title": "Adult Education Instructors", "fit": "Great", "href": ""},
    ],
}

OCCUPATIONS_PAGE_1 = {
    "start": 1,
    "end": 2,
    "total": 3,
    "next": "https://api-v2.onetcenter.org/online/occupations?start=3&end=4",
    "occupation": [
        {"href": "", "code": "11-1011.00", "title": "Chief Executives"},
        {"href": "", "code": "11-1021.00", "title": "General Managers"},
    ],
}

OCCUPATIONS_PAGE_2 = {
    "start": 3,
    "end": 3,
    "total": 3,
    "occupation": [
        {"href": "", "code": "11-1031.00", "title": "Legislators"},
    ],
}


# ---------------------------------------------------------------------------
# Route map — path prefix → canned response
# ---------------------------------------------------------------------------

_ROUTE_MAP: dict[str, Any] = {
    "/online/search": SEARCH_RESPONSE,
    "/online/occupations/25-2021.00/": OCCUPATION_RESPONSE,
    "/online/occupations/25-2021.00/details/knowledge": KNOWLEDGE_RESPONSE,
    "/online/occupations/25-2021.00/details/skills": SKILLS_RESPONSE,
    "/online/occupations/25-2021.00/details/abilities": ABILITIES_RESPONSE,
    "/online/occupations/25-2021.00/details/work_styles": WORK_STYLES_RESPONSE,
    "/online/occupations/25-2021.00/details/interests": INTERESTS_RESPONSE,
    "/online/occupations/25-2021.00/details/tasks": TASKS_RESPONSE,
    "/online/occupations/25-2021.00/details/work_activities": WORK_ACTIVITIES_RESPONSE,
    "/online/occupations/25-2021.00/details/work_context": WORK_CONTEXT_RESPONSE,
    "/online/occupations/25-2021.00/details/detailed_work_activities": (
        DETAILED_WORK_ACTIVITIES_RESPONSE
    ),
    "/online/occupations/25-2021.00/details/education": EDUCATION_RESPONSE,
    "/online/occupations/25-2021.00/details/job_zone": JOB_ZONE_RESPONSE,
    "/online/occupations/25-2021.00/hot_technology": HOT_TECHNOLOGY_RESPONSE,
    "/online/occupations/25-2021.00/details/technology_skills": TECHNOLOGY_SKILLS_RESPONSE,
    "/online/occupations/25-2021.00/details/related_occupations": RELATED_OCCUPATIONS_RESPONSE,
    "/online/crosswalks/military": CROSSWALK_MILITARY_RESPONSE,
    "/taxonomy/active/2010/25-2021.00": TAXONOMY_MAP_RESPONSE,
    "/database": TABLES_RESPONSE,
    "/database/info/essential_skills": TABLE_INFO_RESPONSE,
    "/database/rows/essential_skills": TABLE_ROWS_RESPONSE,
    "/mnm/interestprofiler/questions": PROFILER_QUESTIONS_RESPONSE,
    "/mnm/interestprofiler/results": PROFILER_RESULTS_RESPONSE,
    "/mnm/interestprofiler/careers": PROFILER_CAREERS_RESPONSE,
}


class StubTransport(httpx.BaseTransport):
    """Deterministic HTTP transport that returns canned JSON responses.

    Matches requests by path prefix against _ROUTE_MAP. Supports injecting
    pagination sequences and error responses for retry testing.
    """

    def __init__(self, overrides: dict[str, Any] | None = None) -> None:
        self._overrides = overrides or {}
        self._request_log: list[httpx.Request] = []
        self._call_counts: dict[str, int] = {}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self._request_log.append(request)
        path = request.url.path

        # Check overrides first (for pagination, errors, etc.)
        if path in self._overrides:
            override = self._overrides[path]
            if isinstance(override, list):
                # Sequence of responses — pop the next one
                idx = self._call_counts.get(path, 0)
                self._call_counts[path] = idx + 1
                response_data = override[min(idx, len(override) - 1)]
            else:
                response_data = override

            if isinstance(response_data, int):
                # Bare int = error status code
                return httpx.Response(status_code=response_data)
            return httpx.Response(200, json=response_data)

        # Fall through to route map
        for route_path, response_data in _ROUTE_MAP.items():
            if path.endswith(route_path) or path == route_path:
                return httpx.Response(200, json=response_data)

        return httpx.Response(404, json={"error": f"No stub for {path}"})


@pytest.fixture
def stub_transport() -> StubTransport:
    """Default stub transport with canned responses."""
    return StubTransport()


@pytest.fixture
def onet(stub_transport: StubTransport) -> OnetClient:
    """OnetClient wired to stub transport — no real HTTP calls."""
    return OnetClient(api_key="test-key", transport=stub_transport)


@pytest.fixture
def make_client():
    """Factory: build an OnetClient against a given stub transport."""

    def _make(transport: StubTransport) -> OnetClient:
        return OnetClient(api_key="test-key", transport=transport)

    return _make

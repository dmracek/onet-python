"""Tests for Pydantic response models — validation, defaults, edge cases."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from onet.models import (
    ElementEnvelope,
    Interest,
    JobZone,
    OccupationProfile,
    OccupationRef,
    ScoredElement,
    Task,
    TechnologySkill,
)

# ---------------------------------------------------------------------------
# ScoredElement
# ---------------------------------------------------------------------------


class TestScoredElement:
    def test_full_fields(self) -> None:
        el = ScoredElement(
            id="2.C.7.a",
            name="English Language",
            description="Knowledge of English.",
            importance=97,
        )
        assert el.id == "2.C.7.a"
        assert el.name == "English Language"
        assert el.importance == 97

    def test_defaults(self) -> None:
        el = ScoredElement(id="x", name="Minimal")
        assert el.description == ""
        assert el.importance == 0

    @pytest.mark.parametrize(
        "importance",
        [
            pytest.param(0, id="zero"),
            pytest.param(50, id="mid"),
            pytest.param(100, id="max"),
            pytest.param(33.5, id="float"),
        ],
    )
    def test_accepts_valid_importance_values(self, importance: float) -> None:
        el = ScoredElement(id="x", name="Test", importance=importance)
        assert el.importance == importance


# ---------------------------------------------------------------------------
# Interest
# ---------------------------------------------------------------------------


class TestInterest:
    def test_full_fields(self) -> None:
        i = Interest(id="1.B.1.d", name="Social", description="Helping.", occupational_interest=100)
        assert i.name == "Social"
        assert i.occupational_interest == 100

    def test_defaults_to_zero(self) -> None:
        i = Interest(id="x", name="Minimal")
        assert i.occupational_interest == 0


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


class TestTask:
    def test_full_fields(self) -> None:
        t = Task(id="6744", title="Establish rules.", importance=88, category="Core")
        assert t.title == "Establish rules."
        assert t.category == "Core"

    def test_defaults(self) -> None:
        t = Task(id="x", title="Minimal task")
        assert t.importance == 0
        assert t.category == ""


# ---------------------------------------------------------------------------
# OccupationRef
# ---------------------------------------------------------------------------


class TestOccupationRef:
    def test_from_search_data(self) -> None:
        ref = OccupationRef.model_validate(
            {
                "code": "25-2021.00",
                "title": "Elementary School Teachers",
                "href": "https://api-v2.onetcenter.org/online/occupations/25-2021.00/",
            }
        )
        assert ref.code == "25-2021.00"
        assert ref.href.endswith("/")

    def test_href_defaults_empty(self) -> None:
        ref = OccupationRef(code="11-1011.00", title="Chief Executives")
        assert ref.href == ""


# ---------------------------------------------------------------------------
# JobZone
# ---------------------------------------------------------------------------


class TestJobZone:
    def test_full_fields(self) -> None:
        jz = JobZone(
            code=4,
            title="Job Zone Four",
            education="Bachelor's degree",
            related_experience="Two to four years",
            job_training="Few months to one year",
            job_zone_examples="Sales managers, graphic designers",
            svp_range="(7.0 to < 8.0)",
        )
        assert jz.code == 4
        assert "bachelor" in jz.education.lower()

    def test_defaults(self) -> None:
        jz = JobZone(code=1, title="Minimal")
        assert jz.related_experience == ""
        assert jz.education == ""


# ---------------------------------------------------------------------------
# TechnologySkill
# ---------------------------------------------------------------------------


class TestTechnologySkill:
    @pytest.mark.parametrize(
        "hot",
        [
            pytest.param(True, id="hot-technology"),
            pytest.param(False, id="not-hot"),
        ],
    )
    def test_hot_technology_flag(self, hot: bool) -> None:
        ts = TechnologySkill(
            category_code=43233501,
            category_title="Electronic mail software",
            example_name="Microsoft Outlook",
            hot_technology=hot,
        )
        assert ts.hot_technology == hot

    def test_category_code_is_the_unspsc_int(self) -> None:
        """The API's category `code` is a UNSPSC number, not a string id."""
        ts = TechnologySkill(category_code=43233501, category_title="Email")
        assert ts.category_code == 43233501


# ---------------------------------------------------------------------------
# OccupationProfile
# ---------------------------------------------------------------------------


class TestOccupationProfile:
    def test_empty_profile(self) -> None:
        """Profile with no KSAO data is still valid."""
        p = OccupationProfile(code="00-0000.00", title="Empty")
        assert p.interests == []
        assert p.knowledge == []
        assert p.skills == []
        assert p.abilities == []
        assert p.work_styles == []

    def test_populated_profile(self) -> None:
        p = OccupationProfile(
            code="25-2021.00",
            title="Teacher",
            description="Teaches.",
            interests=[Interest(id="1", name="Social", occupational_interest=100)],
            knowledge=[ScoredElement(id="2", name="English", importance=97)],
            skills=[ScoredElement(id="3", name="Speaking", importance=78)],
            abilities=[ScoredElement(id="4", name="Oral Expression", importance=91)],
            work_styles=[ScoredElement(id="5", name="Dependability", importance=88)],
        )
        assert len(p.interests) == 1
        assert p.interests[0].occupational_interest == 100
        assert p.knowledge[0].importance == 97


# ---------------------------------------------------------------------------
# Response envelopes
# ---------------------------------------------------------------------------


class TestEnvelopeStrictness:
    """The envelopes exist to turn silent data loss into a loud error.

    Three shipped bugs had the same shape: the client read a payload key the
    API does not use, `.get(key, [])` returned the default, and the caller got
    an empty list with no sign anything was wrong. These tests pin the
    behavior that makes that impossible.
    """

    def test_missing_data_key_raises(self) -> None:
        """A renamed data key must raise, not yield an empty list."""
        with pytest.raises(ValidationError, match="element"):
            ElementEnvelope[ScoredElement].model_validate(
                {"start": 1, "end": 2, "total": 2, "occupation": []}
            )

    def test_unexpected_key_raises(self) -> None:
        """An unmodeled top-level key must raise rather than be ignored."""
        with pytest.raises(ValidationError, match="category"):
            ElementEnvelope[ScoredElement].model_validate({"element": [], "category": []})

    def test_empty_data_key_is_allowed(self) -> None:
        """A present-but-empty list is a real answer — O*NET has coverage gaps."""
        page = ElementEnvelope[ScoredElement].model_validate(
            {"start": 1, "end": 0, "total": 0, "element": []}
        )
        assert page.element == []

    def test_next_is_optional(self) -> None:
        """`next` is absent on the last page and on non-paging endpoints."""
        page = ElementEnvelope[ScoredElement].model_validate({"total": 1, "element": []})
        assert page.next is None

    def test_items_stay_lenient(self) -> None:
        """Strictness is on the envelope; rows may gain fields without breaking."""
        page = ElementEnvelope[ScoredElement].model_validate(
            {"element": [{"id": "2.A.1.a", "name": "Reading", "brand_new_field": 1}]}
        )
        assert page.element[0].name == "Reading"

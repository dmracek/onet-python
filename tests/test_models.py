"""Tests for Pydantic response models — validation, defaults, edge cases."""

from __future__ import annotations

import pytest

from onet.models import (
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
            code="25-2021.00",
            title="Job Zone Four",
            education="Bachelor's degree",
            experience="Two to four years",
            job_training="Few months to one year",
            job_zone=4,
            svp_range="7.0 to < 8.0",
        )
        assert jz.job_zone == 4
        assert "bachelor" in jz.education.lower()

    def test_defaults(self) -> None:
        jz = JobZone(code="x", title="Minimal")
        assert jz.job_zone == 0
        assert jz.education == ""


# ---------------------------------------------------------------------------
# TechnologySkill
# ---------------------------------------------------------------------------


class TestTechnologySkill:
    @pytest.mark.parametrize(
        "hot, in_demand",
        [
            pytest.param(True, True, id="hot-and-in-demand"),
            pytest.param(True, False, id="hot-only"),
            pytest.param(False, True, id="in-demand-only"),
            pytest.param(False, False, id="neither"),
        ],
    )
    def test_boolean_flags(self, hot: bool, in_demand: bool) -> None:
        ts = TechnologySkill(
            category_code="11.0",
            category_title="Software",
            example_name="Tool",
            hot_technology=hot,
            in_demand=in_demand,
        )
        assert ts.hot_technology == hot
        assert ts.in_demand == in_demand


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

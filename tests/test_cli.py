"""Tests for O*NET CLI — uses typer CliRunner with stubbed client."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

# Import the CLI app — the test runner invokes commands through it
from onet.cli import app
from onet.client import OnetClient
from onet.models import (
    HotTechnology,
    Interest,
    OccupationProfile,
    OccupationRef,
    ScoredElement,
    TableColumn,
    TableRef,
    Task,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Stub data builders
# ---------------------------------------------------------------------------


def _make_refs(n: int = 2) -> list[OccupationRef]:
    return [
        OccupationRef(code=f"25-{2020 + i}.00", title=f"Teacher Type {i}", href="")
        for i in range(1, n + 1)
    ]


def _make_profile() -> OccupationProfile:
    return OccupationProfile(
        code="25-2021.00",
        title="Elementary School Teachers",
        description="Teach academic and social skills.",
        interests=[
            Interest(id="1", name="Social", occupational_interest=100),
            Interest(id="2", name="Artistic", occupational_interest=48),
        ],
        knowledge=[ScoredElement(id="k1", name="English Language", importance=97)],
        skills=[ScoredElement(id="s1", name="Instructing", importance=81)],
        abilities=[ScoredElement(id="a1", name="Oral Expression", importance=91)],
        work_styles=[ScoredElement(id="w1", name="Dependability", importance=88)],
    )


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearchCommand:
    def test_displays_results(self) -> None:
        with patch.object(OnetClient, "search", return_value=_make_refs()):
            result = runner.invoke(app, ["search", "teacher"])
        assert result.exit_code == 0
        assert "25-2021.00" in result.output
        assert "Teacher Type 1" in result.output

    def test_empty_search(self) -> None:
        with patch.object(OnetClient, "search", return_value=[]):
            result = runner.invoke(app, ["search", "xyznonexistent"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# profile
# ---------------------------------------------------------------------------


class TestProfileCommand:
    def test_by_code(self) -> None:
        with patch.object(OnetClient, "occupation_profile", return_value=_make_profile()):
            result = runner.invoke(app, ["profile", "25-2021.00"])
        assert result.exit_code == 0
        assert "Elementary School Teachers" in result.output
        assert "Social" in result.output
        assert "100" in result.output
        assert "English Language" in result.output

    def test_by_keyword(self) -> None:
        with (
            patch.object(OnetClient, "search", return_value=_make_refs(1)),
            patch.object(OnetClient, "occupation_profile", return_value=_make_profile()),
        ):
            result = runner.invoke(app, ["profile", "--keyword", "teacher"])
        assert result.exit_code == 0
        assert "Elementary School Teachers" in result.output

    def test_keyword_no_results(self) -> None:
        with patch.object(OnetClient, "search", return_value=[]):
            result = runner.invoke(app, ["profile", "--keyword", "xyznonexistent"])
        assert result.exit_code == 1
        assert "No results" in result.output

    def test_no_code_no_keyword(self) -> None:
        result = runner.invoke(app, ["profile"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# tasks
# ---------------------------------------------------------------------------


class TestTasksCommand:
    def test_displays_tasks(self) -> None:
        tasks = [
            Task(id="1", title="Establish rules for behavior.", importance=88, category="Core"),
            Task(id="2", title="Prepare materials.", importance=85, category="Core"),
        ]
        with patch.object(OnetClient, "tasks", return_value=tasks):
            result = runner.invoke(app, ["tasks", "25-2021.00"])
        assert result.exit_code == 0
        assert "Establish rules" in result.output
        assert "88" in result.output


# ---------------------------------------------------------------------------
# tech
# ---------------------------------------------------------------------------


class TestTechCommand:
    def test_displays_hot_tech(self) -> None:
        tech = [
            HotTechnology(
                title="Google Classroom", hot_technology=True, in_demand=True, percentage=25.0
            )
        ]
        with patch.object(OnetClient, "hot_technology", return_value=tech):
            result = runner.invoke(app, ["tech", "25-2021.00"])
        assert result.exit_code == 0
        assert "Google Classroom" in result.output


# ---------------------------------------------------------------------------
# related
# ---------------------------------------------------------------------------


class TestRelatedCommand:
    def test_displays_related(self) -> None:
        with patch.object(OnetClient, "related_occupations", return_value=_make_refs(1)):
            result = runner.invoke(app, ["related", "25-2021.00"])
        assert result.exit_code == 0
        assert "25-2021.00" in result.output


# ---------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------


class TestTablesCommand:
    def test_lists_tables(self) -> None:
        tables = [
            TableRef(id="Skills", title="Skills"),
            TableRef(id="Knowledge", title="Knowledge"),
        ]
        with patch.object(OnetClient, "tables", return_value=tables):
            result = runner.invoke(app, ["tables"])
        assert result.exit_code == 0
        assert "Skills" in result.output
        assert "Knowledge" in result.output


# ---------------------------------------------------------------------------
# table
# ---------------------------------------------------------------------------


class TestTableCommand:
    def test_displays_rows(self) -> None:
        cols = [
            TableColumn(name="code", type="varchar", description="SOC"),
            TableColumn(name="name", type="varchar", description="Skill"),
        ]
        rows = [
            {"code": "25-2021.00", "name": "Reading Comprehension"},
            {"code": "25-2021.00", "name": "Speaking"},
        ]
        with (
            patch.object(OnetClient, "table_info", return_value=cols),
            patch.object(OnetClient, "table_rows", return_value=rows),
        ):
            result = runner.invoke(app, ["table", "Skills"])
        assert result.exit_code == 0
        assert "Reading Comprehension" in result.output
        assert "Speaking" in result.output

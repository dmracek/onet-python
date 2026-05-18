"""Tests for O*NET CLI — uses typer CliRunner with monkeypatched client methods."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

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


@pytest.fixture(autouse=True)
def _stub_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every CLI command instantiates OnetClient — make sure _get_api_key never reads .env."""
    monkeypatch.setenv("ONET_API_KEY", "test-key")


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
    def test_displays_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(OnetClient, "search", lambda *_a, **_k: _make_refs())
        result = runner.invoke(app, ["search", "teacher"])
        assert result.exit_code == 0
        assert "25-2021.00" in result.output
        assert "Teacher Type 1" in result.output

    def test_empty_search(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(OnetClient, "search", lambda *_a, **_k: [])
        result = runner.invoke(app, ["search", "xyznonexistent"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# profile
# ---------------------------------------------------------------------------


class TestProfileCommand:
    def test_by_code(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(OnetClient, "occupation_profile", lambda *_a, **_k: _make_profile())
        result = runner.invoke(app, ["profile", "25-2021.00"])
        assert result.exit_code == 0
        assert "Elementary School Teachers" in result.output
        assert "Social" in result.output
        assert "100" in result.output
        assert "English Language" in result.output

    def test_by_keyword(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(OnetClient, "search", lambda *_a, **_k: _make_refs(1))
        monkeypatch.setattr(OnetClient, "occupation_profile", lambda *_a, **_k: _make_profile())
        result = runner.invoke(app, ["profile", "--keyword", "teacher"])
        assert result.exit_code == 0
        assert "Elementary School Teachers" in result.output

    def test_keyword_no_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(OnetClient, "search", lambda *_a, **_k: [])
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
    def test_displays_tasks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        tasks = [
            Task(id="1", title="Establish rules for behavior.", importance=88, category="Core"),
            Task(id="2", title="Prepare materials.", importance=85, category="Core"),
        ]
        monkeypatch.setattr(OnetClient, "tasks", lambda *_a, **_k: tasks)
        result = runner.invoke(app, ["tasks", "25-2021.00"])
        assert result.exit_code == 0
        assert "Establish rules" in result.output
        assert "88" in result.output


# ---------------------------------------------------------------------------
# tech
# ---------------------------------------------------------------------------


class TestTechCommand:
    def test_displays_hot_tech(self, monkeypatch: pytest.MonkeyPatch) -> None:
        tech = [
            HotTechnology(
                title="Google Classroom", hot_technology=True, in_demand=True, percentage=25.0
            )
        ]
        monkeypatch.setattr(OnetClient, "hot_technology", lambda *_a, **_k: tech)
        result = runner.invoke(app, ["tech", "25-2021.00"])
        assert result.exit_code == 0
        assert "Google Classroom" in result.output


# ---------------------------------------------------------------------------
# related
# ---------------------------------------------------------------------------


class TestRelatedCommand:
    def test_displays_related(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(OnetClient, "related_occupations", lambda *_a, **_k: _make_refs(1))
        result = runner.invoke(app, ["related", "25-2021.00"])
        assert result.exit_code == 0
        assert "25-2021.00" in result.output


# ---------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------


class TestTablesCommand:
    def test_lists_tables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        tables = [
            TableRef(id="Skills", title="Skills"),
            TableRef(id="Knowledge", title="Knowledge"),
        ]
        monkeypatch.setattr(OnetClient, "tables", lambda *_a, **_k: tables)
        result = runner.invoke(app, ["tables"])
        assert result.exit_code == 0
        assert "Skills" in result.output
        assert "Knowledge" in result.output


# ---------------------------------------------------------------------------
# table
# ---------------------------------------------------------------------------


class TestTableCommand:
    def test_displays_rows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cols = [
            TableColumn(name="code", type="varchar", description="SOC"),
            TableColumn(name="name", type="varchar", description="Skill"),
        ]
        rows = [
            {"code": "25-2021.00", "name": "Reading Comprehension"},
            {"code": "25-2021.00", "name": "Speaking"},
        ]
        monkeypatch.setattr(OnetClient, "table_info", lambda *_a, **_k: cols)
        monkeypatch.setattr(OnetClient, "table_rows", lambda *_a, **_k: rows)
        result = runner.invoke(app, ["table", "Skills"])
        assert result.exit_code == 0
        assert "Reading Comprehension" in result.output
        assert "Speaking" in result.output

"""Tests for OnetClient — stubs over mocks, parametrize with ids."""

from __future__ import annotations

import httpx
import pytest

from onet.client import (
    OnetClient,
    OnetHTTPError,
    OnetTransientError,
    _snake_keys,
    _to_snake_case,
)
from onet.models import (
    DetailedWorkActivity,
    Education,
    HotTechnology,
    Interest,
    JobZone,
    MilitaryCrosswalk,
    OccupationDetail,
    OccupationProfile,
    OccupationRef,
    ProfilerCareer,
    ProfilerQuestion,
    ProfilerResult,
    ScoredElement,
    TableColumn,
    TableRef,
    Task,
    TaxonomyMapping,
    TechnologySkill,
    WorkContext,
)

from .conftest import (
    OCCUPATIONS_PAGE_1,
    OCCUPATIONS_PAGE_2,
    StubTransport,
)

# ---------------------------------------------------------------------------
# _to_snake_case
# ---------------------------------------------------------------------------


class TestToSnakeCase:
    @pytest.mark.parametrize(
        "input_str, expected",
        [
            pytest.param("camelCase", "camel_case", id="camel-case"),
            pytest.param("CamelCase", "camel_case", id="pascal-case"),
            pytest.param("HTMLParser", "html_parser", id="acronym-then-word"),
            pytest.param("getHTTPResponse", "get_http_response", id="word-acronym-word"),
            pytest.param("already_snake", "already_snake", id="already-snake"),
            pytest.param("ALLCAPS", "allcaps", id="all-caps-single"),
            pytest.param("occupational_interest", "occupational_interest", id="no-op"),
            pytest.param("kebab-case", "kebab_case", id="kebab-case"),
            pytest.param("with spaces", "with_spaces", id="spaces"),
            pytest.param("O*NET-SOC Code", "o_net_soc_code", id="punctuation-collapse"),
            pytest.param("foo  bar", "foo_bar", id="multiple-spaces"),
        ],
    )
    def test_converts_to_snake_case(self, input_str: str, expected: str) -> None:
        assert _to_snake_case(input_str) == expected


# ---------------------------------------------------------------------------
# _snake_keys
# ---------------------------------------------------------------------------


class TestSnakeKeys:
    def test_flat_dict(self) -> None:
        result = _snake_keys({"firstName": "Ada", "lastName": "Lovelace"})
        assert result == {"first_name": "Ada", "last_name": "Lovelace"}

    def test_nested_dict(self) -> None:
        result = _snake_keys({"outerKey": {"innerKey": "value"}})
        assert result == {"outer_key": {"inner_key": "value"}}

    def test_list_of_dicts(self) -> None:
        result = _snake_keys({"myList": [{"itemName": "a"}, {"itemName": "b"}]})
        assert result == {"my_list": [{"item_name": "a"}, {"item_name": "b"}]}

    def test_preserves_non_dict_list_items(self) -> None:
        result = _snake_keys({"tags": ["alpha", "beta"]})
        assert result == {"tags": ["alpha", "beta"]}

    def test_empty_dict(self) -> None:
        assert _snake_keys({}) == {}


# ---------------------------------------------------------------------------
# _get_api_key
# ---------------------------------------------------------------------------


class TestGetApiKey:
    def test_reads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ONET_API_KEY", "test-key-123")
        from onet.client import _get_api_key

        assert _get_api_key() == "test-key-123"

    def test_raises_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ONET_API_KEY", raising=False)
        monkeypatch.setattr("onet.client.load_dotenv", lambda: None)
        from onet.client import MissingAPIKeyError, _get_api_key

        with pytest.raises(MissingAPIKeyError, match="ONET_API_KEY not set"):
            _get_api_key()


# ---------------------------------------------------------------------------
# OnetClient.__init__
# ---------------------------------------------------------------------------


class TestClientInit:
    def test_accepts_explicit_key(self) -> None:
        client = OnetClient(api_key="explicit-key")
        assert client._api_key == "explicit-key"
        client.close()

    def test_context_manager(self) -> None:
        with OnetClient(api_key="ctx-key") as client:
            assert client._api_key == "ctx-key"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_returns_occupation_refs(self, onet: OnetClient) -> None:
        results = onet.search("teacher")
        assert len(results) == 2
        assert all(isinstance(r, OccupationRef) for r in results)

    def test_first_result_fields(self, onet: OnetClient) -> None:
        result = onet.search("teacher")[0]
        assert result.code == "25-2021.00"
        assert result.title == "Elementary School Teachers, Except Special Education"

    def test_empty_search(self, make_client) -> None:
        transport = StubTransport(
            overrides={
                "/online/search": {"start": 0, "end": 0, "total": 0, "occupation": []},
            }
        )
        with make_client(transport) as client:
            assert client.search("xyznonexistent") == []

    def test_search_all_paginates(self, make_client) -> None:
        """search_all() loops until end >= total."""
        page_1 = {
            "start": 1,
            "end": 2,
            "total": 3,
            "occupation": [
                {"href": "", "code": "25-2021.00", "title": "Elementary"},
                {"href": "", "code": "25-2022.00", "title": "Middle"},
            ],
        }
        page_2 = {
            "start": 3,
            "end": 3,
            "total": 3,
            "occupation": [{"href": "", "code": "25-2031.00", "title": "Secondary"}],
        }
        transport = StubTransport(overrides={"/online/search": [page_1, page_2]})
        with make_client(transport) as client:
            results = client.search_all("teacher", page_size=2)
        assert [r.code for r in results] == ["25-2021.00", "25-2022.00", "25-2031.00"]


# ---------------------------------------------------------------------------
# Occupations
# ---------------------------------------------------------------------------


class TestOccupations:
    def test_occupation_detail(self, onet: OnetClient) -> None:
        occ = onet.occupation("25-2021.00")
        assert isinstance(occ, OccupationDetail)
        assert occ.code == "25-2021.00"
        assert "elementary" in occ.description.lower()
        assert len(occ.sample_of_reported_titles) == 2

    def test_occupations_all_paginates(self, make_client) -> None:
        """Auto-pagination collects items across two pages."""
        transport = StubTransport(
            overrides={
                "/online/occupations": [OCCUPATIONS_PAGE_1, OCCUPATIONS_PAGE_2],
            }
        )
        with make_client(transport) as client:
            results = client.occupations_all(page_size=2)
        assert len(results) == 3
        assert results[0].code == "11-1011.00"
        assert results[2].code == "11-1031.00"


# ---------------------------------------------------------------------------
# KSAO detail sections
# ---------------------------------------------------------------------------


class TestKSAO:
    @pytest.mark.parametrize(
        "method, expected_first_name, expected_first_score",
        [
            pytest.param("knowledge", "English Language", 97, id="knowledge"),
            pytest.param("skills", "Reading Comprehension", 72, id="skills"),
            pytest.param("abilities", "Oral Comprehension", 75, id="abilities"),
            pytest.param("work_styles", "Dependability", 88, id="work-styles"),
            pytest.param("work_activities", "Getting Information", 80, id="work-activities"),
        ],
    )
    def test_returns_scored_elements(
        self,
        onet: OnetClient,
        method: str,
        expected_first_name: str,
        expected_first_score: float,
    ) -> None:
        items = getattr(onet, method)("25-2021.00")
        assert len(items) >= 1
        assert all(isinstance(el, ScoredElement) for el in items)
        first = items[0]
        assert first.name == expected_first_name
        assert first.importance == expected_first_score


# ---------------------------------------------------------------------------
# Interests (RIASEC)
# ---------------------------------------------------------------------------


class TestInterests:
    def test_returns_interest_models(self, onet: OnetClient) -> None:
        items = onet.interests("25-2021.00")
        assert len(items) == 3
        assert all(isinstance(i, Interest) for i in items)

    def test_social_is_dominant(self, onet: OnetClient) -> None:
        items = onet.interests("25-2021.00")
        top = max(items, key=lambda i: i.occupational_interest)
        assert top.name == "Social"
        assert top.occupational_interest == 100


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


class TestTasks:
    def test_returns_task_models(self, onet: OnetClient) -> None:
        items = onet.tasks("25-2021.00")
        assert len(items) == 2
        assert all(isinstance(t, Task) for t in items)

    def test_task_fields(self, onet: OnetClient) -> None:
        task = onet.tasks("25-2021.00")[0]
        assert task.id == "6744"
        assert task.title == "Establish rules for behavior."
        assert task.importance == 88
        assert task.category == "Core"


# ---------------------------------------------------------------------------
# Work context
# ---------------------------------------------------------------------------


class TestWorkContext:
    def test_returns_work_context_models(self, onet: OnetClient) -> None:
        items = onet.work_context("25-2021.00")
        assert len(items) == 1
        assert isinstance(items[0], WorkContext)
        assert items[0].name == "Indoors, Environmentally Controlled"


# ---------------------------------------------------------------------------
# Detailed work activities
# ---------------------------------------------------------------------------


class TestDetailedWorkActivities:
    def test_returns_activity_models(self, onet: OnetClient) -> None:
        items = onet.detailed_work_activities("25-2021.00")
        assert len(items) == 1
        assert isinstance(items[0], DetailedWorkActivity)
        assert items[0].title == "Develop educational programs."


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------


class TestEducation:
    def test_returns_education_models(self, onet: OnetClient) -> None:
        items = onet.education("25-2021.00")
        assert len(items) == 1
        assert isinstance(items[0], Education)
        assert items[0].title == "Bachelor's degree"
        assert items[0].percentage_of_respondents == 82.0


# ---------------------------------------------------------------------------
# Job zone
# ---------------------------------------------------------------------------


class TestJobZone:
    def test_returns_job_zone_model(self, onet: OnetClient) -> None:
        jz = onet.job_zone("25-2021.00")
        assert isinstance(jz, JobZone)
        assert jz.job_zone == 4
        assert "bachelor" in jz.education.lower()


# ---------------------------------------------------------------------------
# Technology
# ---------------------------------------------------------------------------


class TestTechnology:
    def test_hot_technology(self, onet: OnetClient) -> None:
        items = onet.hot_technology("25-2021.00")
        assert len(items) == 1
        assert isinstance(items[0], HotTechnology)
        assert items[0].title == "Google Classroom"
        assert items[0].hot_technology is True

    def test_technology_skills_flattened(self, onet: OnetClient) -> None:
        """Category → example + example_more flattens into one item per tool."""
        items = onet.technology_skills("25-2021.00")
        assert len(items) == 3
        assert all(isinstance(t, TechnologySkill) for t in items)
        assert items[0].category_title == "Computer based training software"
        assert items[0].example_name == "Google Classroom"
        assert items[0].hot_technology is True
        assert items[1].example_name == "Nearpod"
        assert items[2].example_name == "Schoology"  # from example_more


# ---------------------------------------------------------------------------
# Related occupations
# ---------------------------------------------------------------------------


class TestRelatedOccupations:
    def test_returns_occupation_refs(self, onet: OnetClient) -> None:
        items = onet.related_occupations("25-2021.00")
        assert len(items) == 1
        assert isinstance(items[0], OccupationRef)
        assert items[0].code == "25-2022.00"


# ---------------------------------------------------------------------------
# Database tables
# ---------------------------------------------------------------------------


class TestDatabaseTables:
    def test_tables_list(self, onet: OnetClient) -> None:
        items = onet.tables()
        assert len(items) == 2
        assert all(isinstance(t, TableRef) for t in items)
        assert items[0].id == "Skills"

    def test_table_info(self, onet: OnetClient) -> None:
        cols = onet.table_info("Skills")
        assert len(cols) == 4
        assert all(isinstance(c, TableColumn) for c in cols)
        assert cols[0].column_id == "O*NET-SOC Code"
        assert cols[0].title == "O*NET-SOC Code"
        assert cols[0].type == "varchar"

    def test_table_rows(self, onet: OnetClient) -> None:
        rows = onet.table_rows("Skills")
        assert len(rows) == 2
        assert rows[0]["element_name"] == "Reading Comprehension"


# ---------------------------------------------------------------------------
# Crosswalk
# ---------------------------------------------------------------------------


class TestCrosswalk:
    def test_military_crosswalk(self, onet: OnetClient) -> None:
        items = onet.crosswalk_military("infantry")
        assert len(items) == 1
        assert isinstance(items[0], MilitaryCrosswalk)
        assert items[0].code == "25-2021.00"


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------


class TestTaxonomy:
    def test_taxonomy_map(self, onet: OnetClient) -> None:
        items = onet.taxonomy_map("25-2021.00")
        assert len(items) == 1
        assert isinstance(items[0], TaxonomyMapping)


# ---------------------------------------------------------------------------
# Convenience: occupation_profile
# ---------------------------------------------------------------------------


class TestOccupationProfile:
    def test_bundles_all_ksao_and_riasec(self, onet: OnetClient) -> None:
        profile = onet.occupation_profile("25-2021.00")
        assert isinstance(profile, OccupationProfile)
        assert profile.code == "25-2021.00"
        assert profile.title == "Elementary School Teachers, Except Special Education"
        assert len(profile.interests) == 3
        assert len(profile.knowledge) == 2
        assert len(profile.skills) == 2
        assert len(profile.abilities) == 1
        assert len(profile.work_styles) == 1


# ---------------------------------------------------------------------------
# Interest Profiler
# ---------------------------------------------------------------------------


class TestProfilerQuestions:
    def test_returns_questions_with_options(self, onet: OnetClient) -> None:
        result = onet.profiler_questions()
        assert result.total == 4
        assert len(result.questions) == 4
        assert len(result.answer_options) == 5
        assert all(isinstance(q, ProfilerQuestion) for q in result.questions)

    def test_question_fields(self, onet: OnetClient) -> None:
        q = onet.profiler_questions().questions[0]
        assert q.index == 1
        assert q.area == "realistic"
        assert q.text == "Build kitchen cabinets"

    def test_answer_options_are_1_to_5(self, onet: OnetClient) -> None:
        options = onet.profiler_questions().answer_options
        assert [o.value for o in options] == [1, 2, 3, 4, 5]
        assert options[0].name == "Strongly Dislike"
        assert options[4].name == "Strongly Like"


class TestProfilerResults:
    @pytest.mark.parametrize(
        "bad_answers, match",
        [
            pytest.param("2" * 29, "exactly 30 or 60", id="too-short"),
            pytest.param("2" * 61, "exactly 30 or 60", id="too-long"),
            pytest.param("9" * 60, "digits 1-5", id="invalid-digit"),
            pytest.param("a" * 60, "digits 1-5", id="non-digit"),
        ],
    )
    def test_validates_answers(self, onet: OnetClient, bad_answers: str, match: str) -> None:
        with pytest.raises(ValueError, match=match):
            onet.profiler_results(bad_answers)

    def test_returns_six_riasec_dimensions(self, onet: OnetClient) -> None:
        results = onet.profiler_results("2" * 60)
        assert len(results) == 6
        assert all(isinstance(r, ProfilerResult) for r in results)

    def test_scores_match(self, onet: OnetClient) -> None:
        results = onet.profiler_results("2" * 60)
        by_code = {r.code: r.score for r in results}
        assert by_code["social"] == 40
        assert by_code["realistic"] == 10
        assert by_code["investigative"] == 30

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param("realistic", id="R"),
            pytest.param("investigative", id="I"),
            pytest.param("artistic", id="A"),
            pytest.param("social", id="S"),
            pytest.param("enterprising", id="E"),
            pytest.param("conventional", id="C"),
        ],
    )
    def test_all_riasec_codes_present(self, onet: OnetClient, code: str) -> None:
        results = onet.profiler_results("3" * 60)
        codes = {r.code for r in results}
        assert code in codes


class TestProfilerCareers:
    def test_returns_career_matches(self, onet: OnetClient) -> None:
        careers = onet.profiler_careers("2" * 60)
        assert len(careers) == 3
        assert all(isinstance(c, ProfilerCareer) for c in careers)

    def test_career_fields(self, onet: OnetClient) -> None:
        career = onet.profiler_careers("2" * 60)[0]
        assert career.code == "25-2021.00"
        assert career.title == "Elementary School Teachers"
        assert career.fit == "Best"

    @pytest.mark.parametrize(
        "fit_value",
        [
            pytest.param("Best", id="best-fit"),
            pytest.param("Great", id="great-fit"),
        ],
    )
    def test_fit_values(self, onet: OnetClient, fit_value: str) -> None:
        careers = onet.profiler_careers("2" * 60)
        fits = {c.fit for c in careers}
        assert fit_value in fits


# ---------------------------------------------------------------------------
# Retry behavior
# ---------------------------------------------------------------------------


class TestRetry:
    @pytest.fixture(autouse=True)
    def _no_sleep(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Skip backoff delays during retry tests."""
        monkeypatch.setattr("onet.client.time.sleep", lambda _: None)

    @staticmethod
    def _success_response() -> dict[str, object]:
        return {
            "start": 1,
            "end": 1,
            "total": 1,
            "occupation": [
                {"href": "", "code": "11-1011.00", "title": "Chief Executives", "tags": {}}
            ],
        }

    @pytest.mark.parametrize(
        "transient_code",
        [pytest.param(429, id="rate-limit"), pytest.param(500, id="server-error")],
    )
    def test_retries_on_transient(self, make_client, transient_code: int) -> None:
        """Client retries transient status codes and succeeds on second attempt."""
        transport = StubTransport(
            overrides={"/online/search": [transient_code, self._success_response()]}
        )
        with make_client(transport) as client:
            results = client.search("ceo")
        assert len(results) == 1
        assert results[0].code == "11-1011.00"

    def test_raises_transient_after_exhausting(self, make_client) -> None:
        """Persistent 5xx raises OnetTransientError after MAX_RETRIES attempts."""
        transport = StubTransport(overrides={"/online/search": [500, 500, 500]})
        with make_client(transport) as client, pytest.raises(OnetTransientError):
            client.search("ceo")
        assert len(transport._request_log) == 3

    def test_raises_immediately_on_non_transient(self, make_client) -> None:
        """4xx other than 429 surface as OnetHTTPError without retry."""
        transport = StubTransport(overrides={"/online/search": [401]})
        with make_client(transport) as client, pytest.raises(OnetHTTPError) as exc_info:
            client.search("ceo")
        assert exc_info.value.status_code == 401
        assert len(transport._request_log) == 1

    def test_retries_on_request_error(self, make_client) -> None:
        """Network errors (timeouts, connection refused) retry then succeed."""
        attempts = {"n": 0}
        success = self._success_response()

        class FlakyTransport(StubTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                attempts["n"] += 1
                if attempts["n"] == 1:
                    raise httpx.ConnectTimeout("simulated timeout", request=request)
                return httpx.Response(200, json=success)

        with make_client(FlakyTransport()) as client:
            results = client.search("ceo")
        assert attempts["n"] == 2
        assert results[0].code == "11-1011.00"

    def test_honors_retry_after_header(self, make_client, monkeypatch: pytest.MonkeyPatch) -> None:
        """429 with Retry-After header uses that value instead of backoff."""
        sleeps: list[float] = []
        monkeypatch.setattr("onet.client.time.sleep", sleeps.append)
        success = self._success_response()

        class RateLimitedTransport(StubTransport):
            def __init__(self) -> None:
                super().__init__()
                self._n = 0

            def handle_request(self, request: httpx.Request) -> httpx.Response:
                self._n += 1
                if self._n == 1:
                    return httpx.Response(429, headers={"Retry-After": "7"}, json={})
                return httpx.Response(200, json=success)

        with make_client(RateLimitedTransport()) as client:
            client.search("ceo")
        assert sleeps == [7.0]

"""O*NET Web Services API v2 client.

Typed Python client mirroring the full onet2r R package API surface.
Auth via ONET_API_KEY env var, auto-pagination, retry on transient errors.
"""

from __future__ import annotations

import math
import os
import random
import re
import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx
from dotenv import load_dotenv
from pydantic import TypeAdapter

from onet.models import (
    ActivityEnvelope,
    AnswerOption,
    CareerEnvelope,
    CategoryEnvelope,
    DetailedWorkActivity,
    Education,
    EducationEnvelope,
    ElementEnvelope,
    ExampleEnvelope,
    HotTechnology,
    Interest,
    JobZone,
    MatchEnvelope,
    MilitaryCrosswalk,
    OccupationDetail,
    OccupationEnvelope,
    OccupationProfile,
    OccupationRef,
    ProfilerCareer,
    ProfilerQuestion,
    ProfilerQuestions,
    ProfilerQuestionsEnvelope,
    ProfilerResult,
    ProfilerResultsEnvelope,
    RiasecFitResult,
    RowEnvelope,
    ScoredElement,
    SimilarityBreakdown,
    SimilarityResult,
    SkillGapItem,
    SkillGapResult,
    TableColumn,
    TableInfoEnvelope,
    TableRef,
    Task,
    TaskEnvelope,
    TaxonomyEnvelope,
    TaxonomyMapping,
    TechnologyCategory,
    TechnologySkill,
    WorkContext,
    _PagedEnvelope,
)

# `/database` is the one endpoint with a top-level array. Build the adapter
# once — schema analysis has real overhead.
_TABLE_LIST = TypeAdapter(list[TableRef])


class OnetError(Exception):
    """Base class for all onet-python errors."""


class MissingAPIKeyError(OnetError):
    """ONET_API_KEY is not set in the environment."""


class OnetHTTPError(OnetError):
    """Non-transient HTTP error returned by the O*NET API."""

    def __init__(self, status_code: int, path: str, message: str) -> None:
        super().__init__(f"O*NET API returned {status_code} for {path}: {message}")
        self.status_code = status_code
        self.path = path


class OnetTransientError(OnetError):
    """Retries exhausted on a transient network or 5xx error."""


BASE_URL = "https://api-v2.onetcenter.org"

_KSAO_SECTIONS = frozenset({"knowledge", "skills", "abilities", "work_styles", "interests"})
_PROFILER_ANSWER_LENGTHS = frozenset({30, 60})
_PROFILER_ANSWER_DIGITS = frozenset("12345")
_RIASEC_NAMES = ("Realistic", "Investigative", "Artistic", "Social", "Enterprising", "Conventional")
_RIASEC_CODE_TO_NAME = dict(zip("RIASEC", _RIASEC_NAMES, strict=True))

_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.0
_BACKOFF_MAX_SECONDS = 30.0
_BACKOFF_JITTER_SECONDS = 1.0


def _backoff_delay(attempt: int) -> float:
    """Exponential backoff with jitter: ~1s, 2s, 4s, ... capped at 30s."""
    base: float = min(_BACKOFF_BASE_SECONDS * (2**attempt), _BACKOFF_MAX_SECONDS)
    jitter: float = random.uniform(0.0, _BACKOFF_JITTER_SECONDS)
    return base + jitter


def _validate_profiler_answers(answers: str) -> None:
    """Reject obviously-malformed profiler answer strings before hitting the API."""
    if len(answers) not in _PROFILER_ANSWER_LENGTHS:
        raise ValueError(
            f"Profiler answers must be exactly 30 or 60 characters, got {len(answers)}"
        )
    bad = {c for c in answers if c not in _PROFILER_ANSWER_DIGITS}
    if bad:
        raise ValueError(f"Profiler answers must contain only digits 1-5; found: {sorted(bad)}")


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a Retry-After header value as seconds.

    O*NET sends an integer seconds value in practice; HTTP also allows an
    RFC 7231 date. We only handle the seconds form — date-form falls back to
    backoff timing (None return).
    """
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _to_snake_case(s: str) -> str:
    """Convert CamelCase/mixed-case strings to snake_case.

    Splits CamelCase boundaries, lowercases, then collapses any run of
    non-alphanumeric characters (spaces, hyphens, asterisks, etc.) into a
    single underscore. Trailing/leading underscores are stripped. This is
    what `_snake_keys()` applies to response dict keys, so the same function
    must be used to map a `column_id` value like "O*NET-SOC Code" to its
    corresponding row dict key.
    """
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s)
    return s.lower().strip("_")


def _snake_keys(data: Any) -> Any:
    """Recursively convert dict keys to snake_case.

    Accepts any JSON value, not just a dict: `/database` returns a top-level
    array, and assuming a dict root here used to crash the whole call.
    """
    if isinstance(data, dict):
        return {_to_snake_case(k): _snake_keys(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_snake_keys(item) for item in data]
    return data


def _get_api_key() -> str:
    """Read ONET_API_KEY from environment, raising a clear error if missing."""
    load_dotenv()
    key = os.environ.get("ONET_API_KEY", "")
    if not key:
        msg = (
            "ONET_API_KEY not set. Get one at "
            "https://onetcenter.org/developer/ "
            "and add it to your .env file."
        )
        raise MissingAPIKeyError(msg)
    return key


class OnetClient:
    """Typed client for O*NET Web Services API v2.

    Usage::

        from onet import OnetClient

        with OnetClient() as onet:
            results = onet.search("teacher")
            profile = onet.occupation_profile("25-2057.00")
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = BASE_URL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key or _get_api_key()
        self._client = httpx.Client(
            headers={
                "Accept": "application/json",
                "X-API-Key": self._api_key,
            },
            timeout=30,
            transport=transport,
        )

    def __enter__(self) -> OnetClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # --- HTTP layer ---

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET with exponential backoff on transient errors.

        Returns the decoded JSON with keys snake-cased — a dict for most
        endpoints, a list for `/database`. Callers validate it through an
        envelope model rather than indexing it by hand.

        Retries 429 and 5xx status codes plus `httpx.RequestError` (timeouts,
        connection errors). Honors `Retry-After` on 429 responses. Non-transient
        HTTP errors raise `OnetHTTPError`; exhausted retries on transient errors
        raise `OnetTransientError`. Both subclass `OnetError`.
        """
        url = f"{self._base_url}{path}"
        last_transient: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                r = self._client.get(url, params=params)
            except httpx.RequestError as exc:
                last_transient = exc
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_backoff_delay(attempt))
                    continue
                raise OnetTransientError(
                    f"Request to {path} failed after {_MAX_RETRIES} attempts: {exc}"
                ) from exc

            if r.status_code in _RETRY_STATUSES:
                last_transient = httpx.HTTPStatusError(
                    f"Transient {r.status_code}", request=r.request, response=r
                )
                if attempt < _MAX_RETRIES - 1:
                    retry_after = _parse_retry_after(r.headers.get("Retry-After"))
                    delay = retry_after if retry_after is not None else _backoff_delay(attempt)
                    time.sleep(delay)
                    continue
                raise OnetTransientError(
                    f"O*NET API returned {r.status_code} for {path} after {_MAX_RETRIES} attempts"
                ) from last_transient

            if r.status_code >= 400:
                raise OnetHTTPError(r.status_code, path, r.text[:200])

            return _snake_keys(r.json())

        raise OnetTransientError(
            f"Retries exhausted for {path}"
        ) from last_transient  # pragma: no cover

    def _paginate[E: _PagedEnvelope, T](
        self,
        path: str,
        envelope: type[E],
        items: Callable[[E], list[T]],
        page_size: int = 500,
        extra_params: dict[str, Any] | None = None,
    ) -> list[T]:
        """Auto-paginate through a paged endpoint, returning all items.

        `envelope` validates each page and `items` pulls the rows out of it,
        so a renamed payload key raises here instead of quietly ending the
        loop with an empty result.
        """
        collected: list[T] = []
        start = 1
        while True:
            params: dict[str, Any] = {"start": start, "end": start + page_size - 1}
            if extra_params:
                params.update(extra_params)
            page = envelope.model_validate(self._get(path, params=params))
            rows = items(page)
            collected.extend(rows)
            if page.end >= page.total or not rows:
                break
            start = page.end + 1
        return collected

    def _detail_elements[T](
        self,
        code: str,
        section: str,
        envelope: type[ElementEnvelope[T]],
        start: int = 1,
        end: int = 500,
    ) -> list[T]:
        """Fetch and validate one `element`-keyed occupation detail section."""
        page = envelope.model_validate(
            self._get(
                f"/online/occupations/{code}/details/{section}",
                params={"start": start, "end": end},
            )
        )
        return page.element

    # --- Search ---

    def search(self, keyword: str, start: int = 1, end: int = 20) -> list[OccupationRef]:
        """Search occupations by keyword, title, or SOC code (single page)."""
        page = OccupationEnvelope[OccupationRef].model_validate(
            self._get("/online/search", params={"keyword": keyword, "start": start, "end": end})
        )
        return page.occupation

    def search_all(self, keyword: str, page_size: int = 500) -> list[OccupationRef]:
        """Search occupations by keyword, auto-paginated across every page."""
        return self._paginate(
            "/online/search",
            OccupationEnvelope[OccupationRef],
            lambda page: page.occupation,
            page_size=page_size,
            extra_params={"keyword": keyword},
        )

    # --- Occupations ---

    def occupations(self, start: int = 1, end: int = 1000) -> list[OccupationRef]:
        """List occupations (single page)."""
        page = OccupationEnvelope[OccupationRef].model_validate(
            self._get("/online/occupations", params={"start": start, "end": end})
        )
        return page.occupation

    def occupations_all(self, page_size: int = 2000) -> list[OccupationRef]:
        """List all occupations with auto-pagination."""
        return self._paginate(
            "/online/occupations",
            OccupationEnvelope[OccupationRef],
            lambda page: page.occupation,
            page_size,
        )

    def occupation(self, code: str) -> OccupationDetail:
        """Get occupation overview (description, titles)."""
        data = self._get(f"/online/occupations/{code}/")
        return OccupationDetail.model_validate(data)

    # --- KSAO detail sections (scored elements) ---

    def knowledge(self, code: str) -> list[ScoredElement]:
        """Knowledge areas ranked by importance."""
        return self._detail_elements(code, "knowledge", ElementEnvelope[ScoredElement])

    def skills(self, code: str) -> list[ScoredElement]:
        """Skills ranked by importance."""
        return self._detail_elements(code, "skills", ElementEnvelope[ScoredElement])

    def abilities(self, code: str) -> list[ScoredElement]:
        """Abilities ranked by importance."""
        return self._detail_elements(code, "abilities", ElementEnvelope[ScoredElement])

    def work_styles(self, code: str) -> list[ScoredElement]:
        """Work styles ranked by importance."""
        return self._detail_elements(code, "work_styles", ElementEnvelope[ScoredElement])

    def work_activities(self, code: str) -> list[ScoredElement]:
        """Work activities ranked by importance."""
        return self._detail_elements(code, "work_activities", ElementEnvelope[ScoredElement])

    # --- Interests (RIASEC) ---

    def interests(self, code: str) -> list[Interest]:
        """RIASEC/Holland interest codes for an occupation."""
        return self._detail_elements(code, "interests", ElementEnvelope[Interest])

    # --- Tasks ---

    def tasks(self, code: str, start: int = 1, end: int = 100) -> list[Task]:
        """Task statements for an occupation (single page)."""
        page = TaskEnvelope[Task].model_validate(
            self._get(
                f"/online/occupations/{code}/details/tasks",
                params={"start": start, "end": end},
            )
        )
        return page.task

    def tasks_all(self, code: str, page_size: int = 500) -> list[Task]:
        """All task statements for an occupation, auto-paginated."""
        return self._paginate(
            f"/online/occupations/{code}/details/tasks",
            TaskEnvelope[Task],
            lambda page: page.task,
            page_size=page_size,
        )

    # --- Work context ---

    def work_context(self, code: str) -> list[WorkContext]:
        """Work context elements."""
        return self._detail_elements(code, "work_context", ElementEnvelope[WorkContext])

    # --- Detailed work activities ---

    def detailed_work_activities(
        self, code: str, start: int = 1, end: int = 100
    ) -> list[DetailedWorkActivity]:
        """Detailed work activities (single page)."""
        page = ActivityEnvelope[DetailedWorkActivity].model_validate(
            self._get(
                f"/online/occupations/{code}/details/detailed_work_activities",
                params={"start": start, "end": end},
            )
        )
        return page.activity

    def detailed_work_activities_all(
        self, code: str, page_size: int = 500
    ) -> list[DetailedWorkActivity]:
        """All detailed work activities for an occupation, auto-paginated."""
        return self._paginate(
            f"/online/occupations/{code}/details/detailed_work_activities",
            ActivityEnvelope[DetailedWorkActivity],
            lambda page: page.activity,
            page_size=page_size,
        )

    # --- Education ---

    def education(self, code: str) -> list[Education]:
        """Education level distribution."""
        page = EducationEnvelope[Education].model_validate(
            self._get(f"/online/occupations/{code}/details/education")
        )
        return page.response

    # --- Job zone ---

    def job_zone(self, code: str) -> JobZone:
        """Job zone classification (returns single object, not paged)."""
        data = self._get(f"/online/occupations/{code}/details/job_zone")
        return JobZone.model_validate(data)

    # --- Technology ---

    def technology_skills(self, code: str) -> list[TechnologySkill]:
        """Technology skills, flattened from the category → example structure."""
        page = CategoryEnvelope[TechnologyCategory].model_validate(
            self._get(
                f"/online/occupations/{code}/details/technology_skills",
                params={"start": 1, "end": 500},
            )
        )
        return [
            TechnologySkill(
                category_code=category.code,
                category_title=category.title,
                example_name=example.title,
                hot_technology=example.hot_technology,
            )
            for category in page.category
            for example in category.example
        ]

    def hot_technology(self, code: str, start: int = 1, end: int = 50) -> list[HotTechnology]:
        """Hot/in-demand technologies for an occupation (single page)."""
        page = ExampleEnvelope[HotTechnology].model_validate(
            self._get(
                f"/online/occupations/{code}/hot_technology",
                params={"start": start, "end": end},
            )
        )
        return page.example

    def hot_technology_all(self, code: str, page_size: int = 500) -> list[HotTechnology]:
        """All hot technologies for an occupation, auto-paginated."""
        return self._paginate(
            f"/online/occupations/{code}/hot_technology",
            ExampleEnvelope[HotTechnology],
            lambda page: page.example,
            page_size=page_size,
        )

    # --- Related occupations ---

    def related_occupations(self, code: str) -> list[OccupationRef]:
        """Occupations related to the given one."""
        page = OccupationEnvelope[OccupationRef].model_validate(
            self._get(f"/online/occupations/{code}/details/related_occupations")
        )
        return page.occupation

    # --- Database tables ---

    def tables(self) -> list[TableRef]:
        """List all available database tables.

        `/database` is the one endpoint with a top-level JSON array, so it is
        validated with a TypeAdapter rather than an envelope model.
        """
        return _TABLE_LIST.validate_python(self._get("/database"))

    def table_info(self, table_id: str) -> list[TableColumn]:
        """Column metadata for a database table.

        `table_id` is the snake_case identifier from `tables()` — e.g.
        `essential_skills` or `occupation_data`. Display titles like "Skills"
        are not valid and the API rejects them with a 422.
        """
        page = TableInfoEnvelope[TableColumn].model_validate(
            self._get(f"/database/info/{table_id}")
        )
        return page.column

    def table_rows(self, table_id: str, page_size: int = 2000) -> list[dict[str, Any]]:
        """All rows from a database table, auto-paginated. Returns raw dicts."""
        return self._paginate(
            f"/database/rows/{table_id}",
            RowEnvelope,
            lambda page: page.row,
            page_size=page_size,
        )

    # --- Crosswalks ---

    def crosswalk_military(
        self, keyword: str, start: int = 1, end: int = 20
    ) -> list[MilitaryCrosswalk]:
        """Military-to-civilian occupation crosswalk search (single page)."""
        page = MatchEnvelope[MilitaryCrosswalk].model_validate(
            self._get(
                "/online/crosswalks/military",
                params={"keyword": keyword, "start": start, "end": end},
            )
        )
        return page.match

    def crosswalk_military_all(self, keyword: str, page_size: int = 500) -> list[MilitaryCrosswalk]:
        """Full military crosswalk search results, auto-paginated."""
        return self._paginate(
            "/online/crosswalks/military",
            MatchEnvelope[MilitaryCrosswalk],
            lambda page: page.match,
            page_size=page_size,
            extra_params={"keyword": keyword},
        )

    # --- Taxonomy ---

    def taxonomy_map(
        self,
        code: str,
        from_version: str = "active",
        to_version: str = "2010",
    ) -> list[TaxonomyMapping]:
        """Map a SOC code between taxonomy versions."""
        page = TaxonomyEnvelope[TaxonomyMapping].model_validate(
            self._get(f"/taxonomy/{from_version}/{to_version}/{code}")
        )
        return page.occupation

    # --- Interest Profiler ---

    def profiler_questions(self, version: str = "questions") -> ProfilerQuestions:
        """Fetch Interest Profiler items.

        Args:
            version: "questions" for 60-item Short Form,
                     "questions_30" for 30-item Mini-IP.
        """
        envelope = ProfilerQuestionsEnvelope[ProfilerQuestion, AnswerOption]
        all_questions: list[ProfilerQuestion] = []
        answer_options: list[AnswerOption] = []
        total = 0
        start = 1
        while True:
            page = envelope.model_validate(
                self._get(
                    f"/mnm/interestprofiler/{version}", params={"start": start, "end": start + 59}
                )
            )
            if not answer_options:
                answer_options = page.answer_option
                total = page.total
            all_questions.extend(page.question)
            if page.end >= page.total or not page.question:
                break
            start = page.end + 1
        return ProfilerQuestions(
            total=total, answer_options=answer_options, questions=all_questions
        )

    def profiler_results(self, answers: str) -> list[ProfilerResult]:
        """Score a completed Interest Profiler.

        Args:
            answers: String of digits (1-5), one per item.
                     60 chars for Short Form, 30 for Mini-IP.
        """
        _validate_profiler_answers(answers)
        page = ProfilerResultsEnvelope[ProfilerResult].model_validate(
            self._get("/mnm/interestprofiler/results", params={"answers": answers})
        )
        return page.result

    def profiler_careers(
        self, answers: str, start: int = 1, end: int = 100
    ) -> list[ProfilerCareer]:
        """Get career matches for a completed Interest Profiler (single page).

        Args:
            answers: String of digits (1-5), one per item.
        """
        _validate_profiler_answers(answers)
        page = CareerEnvelope[ProfilerCareer].model_validate(
            self._get(
                "/mnm/interestprofiler/careers",
                params={"answers": answers, "start": start, "end": end},
            )
        )
        return page.career

    def profiler_careers_all(self, answers: str, page_size: int = 500) -> list[ProfilerCareer]:
        """All career matches for a completed Interest Profiler, auto-paginated."""
        _validate_profiler_answers(answers)
        return self._paginate(
            "/mnm/interestprofiler/careers",
            CareerEnvelope[ProfilerCareer],
            lambda page: page.career,
            page_size=page_size,
            extra_params={"answers": answers},
        )

    # --- Convenience: bundled profile ---

    # --- Computed analysis ---

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Cosine similarity between two equal-length vectors. Returns 0.0 for zero vectors."""
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _align_scored_vectors(
        items_a: list[ScoredElement],
        items_b: list[ScoredElement],
    ) -> tuple[list[float], list[float]]:
        """Align two scored element lists into equal-length vectors by element name."""
        all_names = sorted({el.name for el in items_a} | {el.name for el in items_b})
        map_a = {el.name: el.importance for el in items_a}
        map_b = {el.name: el.importance for el in items_b}
        vec_a = [map_a.get(n, 0.0) for n in all_names]
        vec_b = [map_b.get(n, 0.0) for n in all_names]
        return vec_a, vec_b

    def skill_gap(self, from_code: str, to_code: str) -> SkillGapResult:
        """Compute KSAO gaps between a source and target occupation.

        Returns elements where the target scores higher (gaps you'd need to
        close) and where the source scores higher (existing strengths).
        """
        from_prof = self.occupation_profile(from_code)
        to_prof = self.occupation_profile(to_code)

        sections = [
            ("knowledge", from_prof.knowledge, to_prof.knowledge),
            ("skills", from_prof.skills, to_prof.skills),
            ("abilities", from_prof.abilities, to_prof.abilities),
            ("work_styles", from_prof.work_styles, to_prof.work_styles),
        ]

        gaps: list[SkillGapItem] = []
        strengths: list[SkillGapItem] = []

        for section_name, from_items, to_items in sections:
            from_map = {el.name: el.importance for el in from_items}
            to_map = {el.name: el.importance for el in to_items}
            all_names = sorted(set(from_map) | set(to_map))

            for name in all_names:
                fs = from_map.get(name, 0.0)
                ts = to_map.get(name, 0.0)
                diff = ts - fs
                item = SkillGapItem(
                    name=name,
                    section=section_name,
                    from_score=fs,
                    to_score=ts,
                    gap=abs(diff),
                )
                if diff > 0:
                    gaps.append(item)
                elif diff < 0:
                    strengths.append(item)

        gaps.sort(key=lambda x: x.gap, reverse=True)
        strengths.sort(key=lambda x: x.gap, reverse=True)

        return SkillGapResult(
            from_code=from_code,
            from_title=from_prof.title,
            to_code=to_code,
            to_title=to_prof.title,
            gaps=gaps,
            strengths=strengths,
        )

    def profile_similarity(self, code_a: str, code_b: str) -> SimilarityResult:
        """Cosine similarity between two occupations across all KSAO domains.

        Returns an overall score (0-1) and per-domain breakdown.
        """
        prof_a = self.occupation_profile(code_a)
        prof_b = self.occupation_profile(code_b)

        domain_scores: dict[str, float] = {}
        all_vec_a: list[float] = []
        all_vec_b: list[float] = []

        for domain in ("knowledge", "skills", "abilities", "work_styles"):
            items_a: list[ScoredElement] = getattr(prof_a, domain)
            items_b: list[ScoredElement] = getattr(prof_b, domain)
            vec_a, vec_b = self._align_scored_vectors(items_a, items_b)
            domain_scores[domain] = self._cosine_similarity(vec_a, vec_b)
            all_vec_a.extend(vec_a)
            all_vec_b.extend(vec_b)

        # Interests use occupational_interest, not importance
        int_names = sorted({i.name for i in prof_a.interests} | {i.name for i in prof_b.interests})
        int_map_a = {i.name: i.occupational_interest for i in prof_a.interests}
        int_map_b = {i.name: i.occupational_interest for i in prof_b.interests}
        int_vec_a = [int_map_a.get(n, 0.0) for n in int_names]
        int_vec_b = [int_map_b.get(n, 0.0) for n in int_names]
        domain_scores["interests"] = self._cosine_similarity(int_vec_a, int_vec_b)
        all_vec_a.extend(int_vec_a)
        all_vec_b.extend(int_vec_b)

        return SimilarityResult(
            code_a=code_a,
            code_b=code_b,
            overall=self._cosine_similarity(all_vec_a, all_vec_b),
            breakdown=SimilarityBreakdown(**domain_scores),
        )

    def riasec_fit(
        self,
        person_scores: Mapping[str, float],
        code: str,
    ) -> RiasecFitResult:
        """Compute fit between a person's RIASEC scores and an occupation.

        Args:
            person_scores: Dict mapping RIASEC codes to scores.
                           Keys can be full names ("Realistic"), single
                           letters ("R"), or lowercase variants. Values on
                           any scale — they get normalized internally.
            code: SOC occupation code.

        Raises:
            ValueError: If `person_scores` is empty or contains no recognized
                        RIASEC keys.
        """
        if not person_scores:
            raise ValueError("person_scores must contain at least one RIASEC dimension")

        canonical_lower = {name.lower(): name for name in _RIASEC_NAMES}
        normalized: dict[str, float] = {}
        unrecognized: list[str] = []
        for k, v in person_scores.items():
            full_name = _RIASEC_CODE_TO_NAME.get(k.upper(), k)
            canonical = canonical_lower.get(full_name.lower())
            if canonical is None:
                unrecognized.append(k)
            else:
                normalized[canonical] = float(v)

        if not normalized:
            raise ValueError(
                f"No recognized RIASEC keys in {list(person_scores)}. "
                f"Expected single letters (R/I/A/S/E/C) or full names."
            )

        occ = self.occupation(code)
        occ_interests = self.interests(code)
        occ_map = {i.name: i.occupational_interest for i in occ_interests}

        person_vec = [normalized.get(n, 0.0) for n in _RIASEC_NAMES]
        occ_vec = [occ_map.get(n, 0.0) for n in _RIASEC_NAMES]

        score = self._cosine_similarity(person_vec, occ_vec)

        if score >= 0.85:
            fit = "strong"
        elif score >= 0.65:
            fit = "good"
        elif score >= 0.45:
            fit = "moderate"
        else:
            fit = "weak"

        return RiasecFitResult(
            code=code,
            title=occ.title,
            score=round(score, 3),
            fit=fit,
            person_profile={n: normalized.get(n, 0.0) for n in _RIASEC_NAMES},
            occupation_profile={n: occ_map.get(n, 0.0) for n in _RIASEC_NAMES},
        )

    def to_dataframe(
        self,
        codes: list[str],
        sections: list[str] | None = None,
    ) -> Any:
        """Export KSAO scores for multiple occupations as a pandas DataFrame.

        Each row is an occupation, columns are element importance scores
        prefixed by section (e.g., "knowledge_english_language").

        Args:
            codes: List of SOC codes to fetch.
            sections: Which KSAO sections to include. Defaults to all four
                      plus interests. Options: "knowledge", "skills",
                      "abilities", "work_styles", "interests".

        Returns:
            pandas.DataFrame with columns: code, title, plus one column per
            scored element.

        Raises:
            ImportError: If pandas is not installed.
            ValueError: If `sections` contains an unrecognized name.
        """
        try:
            import pandas as pd
        except ImportError as err:
            raise ImportError(
                "pandas is required for to_dataframe(). Install it with: pip install pandas"
            ) from err

        if sections is None:
            sections = list(_KSAO_SECTIONS)
        else:
            invalid = set(sections) - _KSAO_SECTIONS
            if invalid:
                raise ValueError(
                    f"Unknown sections: {sorted(invalid)}. Valid options: {sorted(_KSAO_SECTIONS)}"
                )

        rows: list[dict[str, Any]] = []
        for code in codes:
            profile = self.occupation_profile(code)
            row: dict[str, Any] = {"code": profile.code, "title": profile.title}

            for section in sections:
                if section == "interests":
                    for interest_item in profile.interests:
                        col = f"interest_{_to_snake_case(interest_item.name)}"
                        row[col] = interest_item.occupational_interest
                else:
                    scored_items: list[ScoredElement] = getattr(profile, section, [])
                    for scored_item in scored_items:
                        col = f"{section}_{_to_snake_case(scored_item.name)}"
                        row[col] = scored_item.importance

            rows.append(row)

        return pd.DataFrame(rows).fillna(0.0)

    # --- Convenience: bundled profile ---

    def occupation_profile(self, code: str) -> OccupationProfile:
        """Fetch full KSAO + RIASEC profile in one call (5 API requests)."""
        occ = self.occupation(code)
        return OccupationProfile(
            code=occ.code,
            title=occ.title,
            description=occ.description,
            interests=self.interests(code),
            knowledge=self.knowledge(code),
            skills=self.skills(code),
            abilities=self.abilities(code),
            work_styles=self.work_styles(code),
        )

"""O*NET Web Services API v2 client.

Typed Python client mirroring the full onet2r R package API surface.
Auth via ONET_API_KEY env var, auto-pagination, retry on transient errors.
"""

from __future__ import annotations

import math
import os
import re
from collections.abc import Mapping
from typing import Any

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel as _BaseModel

from onet.models import (
    AnswerOption,
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
    ProfilerQuestions,
    ProfilerResult,
    RiasecFitResult,
    ScoredElement,
    SimilarityBreakdown,
    SimilarityResult,
    SkillGapItem,
    SkillGapResult,
    TableColumn,
    TableRef,
    Task,
    TaxonomyMapping,
    TechnologySkill,
    WorkContext,
)


class OnetError(Exception):
    """Base class for all onet-python errors."""


class MissingAPIKeyError(OnetError):
    """ONET_API_KEY is not set in the environment."""


BASE_URL = "https://api-v2.onetcenter.org"

# Transient status codes worth retrying
_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3


def _to_snake_case(s: str) -> str:
    """Convert CamelCase or mixed-case string to snake_case."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.lower().replace(" ", "_").replace("-", "_")


def _snake_keys(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively convert all dict keys to snake_case."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        sk = _to_snake_case(k)
        if isinstance(v, dict):
            out[sk] = _snake_keys(v)
        elif isinstance(v, list):
            out[sk] = [_snake_keys(i) if isinstance(i, dict) else i for i in v]
        else:
            out[sk] = v
    return out


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

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET with retry on transient errors."""
        url = f"{self._base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                r = self._client.get(url, params=params)
                if r.status_code in _RETRY_STATUSES and attempt < _MAX_RETRIES - 1:
                    continue
                r.raise_for_status()
                return _snake_keys(r.json())
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code not in _RETRY_STATUSES:
                    raise
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"Retries exhausted for {path} with no captured exception")

    def _paginate[T: _BaseModel](
        self,
        path: str,
        item_key: str,
        model: type[T],
        page_size: int = 500,
    ) -> list[T]:
        """Auto-paginate through a paged endpoint, returning all items."""
        items: list[T] = []
        start = 1
        while True:
            data = self._get(path, params={"start": start, "end": start + page_size - 1})
            raw_items = data.get(item_key, [])
            items.extend(model.model_validate(el) for el in raw_items)
            total = data.get("total", 0)
            end = data.get("end", 0)
            if end >= total or not raw_items:
                break
            start = end + 1
        return items

    def _detail_elements(
        self,
        code: str,
        section: str,
        start: int = 1,
        end: int = 500,
    ) -> list[dict[str, Any]]:
        """Fetch element list from an occupation detail section."""
        data = self._get(
            f"/online/occupations/{code}/details/{section}",
            params={"start": start, "end": end},
        )
        elements: list[dict[str, Any]] = data.get("element", [])
        return elements

    # --- Search ---

    def search(self, keyword: str, start: int = 1, end: int = 20) -> list[OccupationRef]:
        """Search occupations by keyword, title, or SOC code."""
        data = self._get("/online/search", params={"keyword": keyword, "start": start, "end": end})
        return [OccupationRef.model_validate(o) for o in data.get("occupation", [])]

    # --- Occupations ---

    def occupations(self, start: int = 1, end: int = 1000) -> list[OccupationRef]:
        """List occupations (single page)."""
        data = self._get("/online/occupations", params={"start": start, "end": end})
        return [OccupationRef.model_validate(o) for o in data.get("occupation", [])]

    def occupations_all(self, page_size: int = 2000) -> list[OccupationRef]:
        """List all occupations with auto-pagination."""
        return self._paginate("/online/occupations", "occupation", OccupationRef, page_size)

    def occupation(self, code: str) -> OccupationDetail:
        """Get occupation overview (description, titles)."""
        data = self._get(f"/online/occupations/{code}/")
        return OccupationDetail.model_validate(data)

    # --- KSAO detail sections (scored elements) ---

    def knowledge(self, code: str) -> list[ScoredElement]:
        """Knowledge areas ranked by importance."""
        return [ScoredElement.model_validate(el) for el in self._detail_elements(code, "knowledge")]

    def skills(self, code: str) -> list[ScoredElement]:
        """Skills ranked by importance."""
        return [ScoredElement.model_validate(el) for el in self._detail_elements(code, "skills")]

    def abilities(self, code: str) -> list[ScoredElement]:
        """Abilities ranked by importance."""
        return [ScoredElement.model_validate(el) for el in self._detail_elements(code, "abilities")]

    def work_styles(self, code: str) -> list[ScoredElement]:
        """Work styles ranked by importance."""
        return [
            ScoredElement.model_validate(el) for el in self._detail_elements(code, "work_styles")
        ]

    def work_activities(self, code: str) -> list[ScoredElement]:
        """Work activities ranked by importance."""
        return [
            ScoredElement.model_validate(el)
            for el in self._detail_elements(code, "work_activities")
        ]

    # --- Interests (RIASEC) ---

    def interests(self, code: str) -> list[Interest]:
        """RIASEC/Holland interest codes for an occupation."""
        elements = self._detail_elements(code, "interests")
        return [Interest.model_validate(el) for el in elements]

    # --- Tasks ---

    def tasks(self, code: str, start: int = 1, end: int = 100) -> list[Task]:
        """Task statements for an occupation."""
        data = self._get(
            f"/online/occupations/{code}/details/tasks",
            params={"start": start, "end": end},
        )
        return [Task.model_validate(t) for t in data.get("task", [])]

    # --- Work context ---

    def work_context(self, code: str) -> list[WorkContext]:
        """Work context elements."""
        elements = self._detail_elements(code, "work_context")
        return [WorkContext.model_validate(el) for el in elements]

    # --- Detailed work activities ---

    def detailed_work_activities(
        self, code: str, start: int = 1, end: int = 100
    ) -> list[DetailedWorkActivity]:
        """Detailed work activities."""
        data = self._get(
            f"/online/occupations/{code}/details/detailed_work_activities",
            params={"start": start, "end": end},
        )
        return [DetailedWorkActivity.model_validate(a) for a in data.get("activity", [])]

    # --- Education ---

    def education(self, code: str) -> list[Education]:
        """Education level distribution."""
        data = self._get(f"/online/occupations/{code}/details/education")
        return [Education.model_validate(e) for e in data.get("response", [])]

    # --- Job zone ---

    def job_zone(self, code: str) -> JobZone:
        """Job zone classification (returns single object, not paged)."""
        data = self._get(f"/online/occupations/{code}/details/job_zone")
        return JobZone.model_validate(data)

    # --- Technology ---

    def technology_skills(self, code: str) -> list[TechnologySkill]:
        """Technology skills, flattened from category → example structure."""
        elements = self._detail_elements(code, "technology_skills")
        results: list[TechnologySkill] = []
        for el in elements:
            cat_code = el.get("id", "")
            cat_title = el.get("name", "")
            for ex in el.get("example", []):
                results.append(
                    TechnologySkill(
                        category_code=cat_code,
                        category_title=cat_title,
                        example_name=ex.get("name", ""),
                        hot_technology=ex.get("hot_technology", False),
                        in_demand=ex.get("in_demand", False),
                    )
                )
        return results

    def hot_technology(self, code: str, start: int = 1, end: int = 50) -> list[HotTechnology]:
        """Hot/in-demand technologies for an occupation."""
        data = self._get(
            f"/online/occupations/{code}/hot_technology",
            params={"start": start, "end": end},
        )
        return [HotTechnology.model_validate(ex) for ex in data.get("example", [])]

    # --- Related occupations ---

    def related_occupations(self, code: str) -> list[OccupationRef]:
        """Occupations related to the given one."""
        data = self._get(f"/online/occupations/{code}/details/related_occupations")
        return [OccupationRef.model_validate(o) for o in data.get("occupation", [])]

    # --- Database tables ---

    def tables(self) -> list[TableRef]:
        """List all available database tables."""
        data = self._get("/database")
        return [TableRef.model_validate(t) for t in data.get("table", [])]

    def table_info(self, table_id: str) -> list[TableColumn]:
        """Column metadata for a database table."""
        data = self._get(f"/database/info/{table_id}")
        return [TableColumn.model_validate(c) for c in data.get("column", [])]

    def table_rows(self, table_id: str, page_size: int = 2000) -> list[dict[str, Any]]:
        """All rows from a database table, auto-paginated. Returns raw dicts."""
        rows: list[dict[str, Any]] = []
        start = 1
        while True:
            data = self._get(
                f"/database/rows/{table_id}", params={"start": start, "end": start + page_size - 1}
            )
            raw = data.get("row", [])
            rows.extend(raw)
            total = data.get("total", 0)
            end_idx = data.get("end", 0)
            if end_idx >= total or not raw:
                break
            start = end_idx + 1
        return rows

    # --- Crosswalks ---

    def crosswalk_military(
        self, keyword: str, start: int = 1, end: int = 20
    ) -> list[MilitaryCrosswalk]:
        """Military-to-civilian occupation crosswalk search."""
        data = self._get(
            "/online/crosswalks/military",
            params={"keyword": keyword, "start": start, "end": end},
        )
        return [MilitaryCrosswalk.model_validate(o) for o in data.get("occupation", [])]

    # --- Taxonomy ---

    def taxonomy_map(
        self,
        code: str,
        from_version: str = "active",
        to_version: str = "2010",
    ) -> list[TaxonomyMapping]:
        """Map a SOC code between taxonomy versions."""
        data = self._get(f"/taxonomy/{from_version}/{to_version}/{code}")
        return [TaxonomyMapping.model_validate(o) for o in data.get("occupation", [])]

    # --- Interest Profiler ---

    def profiler_questions(self, version: str = "questions") -> ProfilerQuestions:
        """Fetch Interest Profiler items.

        Args:
            version: "questions" for 60-item Short Form,
                     "questions_30" for 30-item Mini-IP.
        """
        all_questions: list[ProfilerQuestion] = []
        answer_options: list[AnswerOption] = []
        total = 0
        start = 1
        while True:
            data = self._get(
                f"/mnm/interestprofiler/{version}", params={"start": start, "end": start + 59}
            )
            if not answer_options:
                answer_options = [
                    AnswerOption.model_validate(o) for o in data.get("answer_option", [])
                ]
                total = data.get("total", 0)
            all_questions.extend(
                ProfilerQuestion.model_validate(q) for q in data.get("question", [])
            )
            if data.get("end", 0) >= data.get("total", 0) or not data.get("question"):
                break
            start = data["end"] + 1
        return ProfilerQuestions(
            total=total, answer_options=answer_options, questions=all_questions
        )

    def profiler_results(self, answers: str) -> list[ProfilerResult]:
        """Score a completed Interest Profiler.

        Args:
            answers: String of digits (1-5), one per item.
                     60 chars for Short Form, 30 for Mini-IP.
        """
        data = self._get("/mnm/interestprofiler/results", params={"answers": answers})
        return [ProfilerResult.model_validate(r) for r in data.get("result", [])]

    def profiler_careers(
        self, answers: str, start: int = 1, end: int = 100
    ) -> list[ProfilerCareer]:
        """Get career matches for a completed Interest Profiler.

        Args:
            answers: String of digits (1-5), one per item.
        """
        data = self._get(
            "/mnm/interestprofiler/careers",
            params={"answers": answers, "start": start, "end": end},
        )
        return [ProfilerCareer.model_validate(c) for c in data.get("career", [])]

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
                           Keys can be full names ("Realistic") or single
                           letters ("R"). Values on any scale — they get
                           normalized internally.
            code: SOC occupation code.
        """
        # Normalize key names to full RIASEC labels
        code_map = {
            "R": "Realistic",
            "I": "Investigative",
            "A": "Artistic",
            "S": "Social",
            "E": "Enterprising",
            "C": "Conventional",
        }
        riasec_order = [
            "Realistic",
            "Investigative",
            "Artistic",
            "Social",
            "Enterprising",
            "Conventional",
        ]

        normalized: dict[str, float] = {}
        for k, v in person_scores.items():
            full_name = code_map.get(k.upper(), k)
            # Also accept lowercase full names
            for name in riasec_order:
                if full_name.lower() == name.lower():
                    normalized[name] = float(v)
                    break

        occ = self.occupation(code)
        occ_interests = self.interests(code)
        occ_map = {i.name: i.occupational_interest for i in occ_interests}

        person_vec = [normalized.get(n, 0.0) for n in riasec_order]
        occ_vec = [occ_map.get(n, 0.0) for n in riasec_order]

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
            person_profile={n: normalized.get(n, 0.0) for n in riasec_order},
            occupation_profile={n: occ_map.get(n, 0.0) for n in riasec_order},
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
        """
        try:
            import pandas as pd
        except ImportError as err:
            raise ImportError(
                "pandas is required for to_dataframe(). Install it with: pip install pandas"
            ) from err

        if sections is None:
            sections = ["knowledge", "skills", "abilities", "work_styles", "interests"]

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

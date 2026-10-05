"""Pydantic response models for O*NET Web Services API v2."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# --- Pagination ---


class PaginatedResponse[T](BaseModel):
    """Generic paginated response wrapper."""

    start: int = 1
    end: int = 0
    total: int = 0
    items: list[T] = Field(default_factory=list)


# --- Response envelopes ---
#
# Every list endpoint wraps its rows in an envelope whose data key varies
# (`element`, `occupation`, `task`, ...). Parsing those by hand with
# `data.get(key, [])` is what let three separate bugs ship: when the key was
# wrong, the default `[]` swallowed the whole payload and the client returned
# an empty list with no error.
#
# So the envelopes are models too, and they are strict on purpose:
#   - `extra="forbid"` — an unexpected or renamed key raises instead of
#     being ignored.
#   - the data field is REQUIRED (no default) — a missing key raises instead
#     of yielding [].
#
# Item models stay lenient (pydantic's default `ignore`) so O*NET can add
# fields to rows without breaking callers. Strictness belongs on the shape we
# depend on, not on the shape they own.


class _Envelope(BaseModel):
    """Base for response envelopes. Strict by design — see module notes."""

    model_config = ConfigDict(extra="forbid")


class _PagedEnvelope(_Envelope):
    """Envelope for endpoints that paginate.

    `next` is absent on the last page (and on endpoints that never page), so
    it is the one optional member of the pagination block.
    """

    start: int = 1
    end: int = 0
    total: int = 0
    next: str | None = None


class ElementEnvelope[T](_PagedEnvelope):
    """knowledge, skills, abilities, work_styles, work_activities, interests, work_context."""

    element: list[T]


class OccupationEnvelope[T](_PagedEnvelope):
    """search, occupations, related_occupations."""

    occupation: list[T]


class TaskEnvelope[T](_PagedEnvelope):
    """tasks."""

    task: list[T]


class ActivityEnvelope[T](_PagedEnvelope):
    """detailed_work_activities."""

    activity: list[T]


class ExampleEnvelope[T](_PagedEnvelope):
    """hot_technology."""

    example: list[T]


class MatchEnvelope[T](_PagedEnvelope):
    """crosswalks/military."""

    match: list[T]


class CareerEnvelope[T](_PagedEnvelope):
    """interestprofiler/careers."""

    career: list[T]


class RowEnvelope(_PagedEnvelope):
    """database/rows/{table_id} — columns vary per table, so rows stay dicts."""

    row: list[dict[str, Any]]


class HotTechnologyRef(BaseModel):
    """Pointer to an occupation's hot-technology list, embedded in tech skills."""

    total: int = 0
    href: str = ""


class CategoryEnvelope[T](_PagedEnvelope):
    """details/technology_skills — note the data key is `category`, not `element`."""

    hot_technology: HotTechnologyRef = Field(default_factory=HotTechnologyRef)
    category: list[T]


class EducationEnvelope[T](_Envelope):
    """details/education — returns no pagination block at all."""

    response: list[T]


class TaxonomyEnvelope[T](_Envelope):
    """taxonomy/{from}/{to}/{code}."""

    code: str
    title: str
    description: str = ""
    occupation: list[T]


class TableInfoEnvelope[T](_Envelope):
    """database/info/{table_id}."""

    table_id: str
    title: str = ""
    description: str = ""
    rows: str = ""
    data_dictionary: str = ""
    download: dict[str, str] = Field(default_factory=dict)
    column: list[T]


class ProfilerQuestionsEnvelope[T, O](_PagedEnvelope):
    """interestprofiler/questions."""

    answer_option: list[O]
    question: list[T]


class ProfilerResultsEnvelope[T](_Envelope):
    """interestprofiler/results — no pagination, plus a `careers` link."""

    careers: str = ""
    result: list[T]


# --- Search ---


class OccupationRef(BaseModel):
    """Minimal occupation reference (search results, related occupations)."""

    code: str
    title: str
    href: str = ""


# --- Occupation detail ---


class OccupationDetail(BaseModel):
    """Full occupation overview."""

    code: str
    title: str
    description: str = ""
    sample_of_reported_titles: list[str] = Field(default_factory=list)


# --- Scored elements (knowledge, skills, abilities, work styles, work activities) ---


class ScoredElement(BaseModel):
    """An element with an importance score (0-100)."""

    id: str
    name: str
    description: str = ""
    importance: float = 0


# --- Interests (RIASEC) ---


class Interest(BaseModel):
    """RIASEC/Holland interest code with occupational interest score."""

    id: str
    name: str
    description: str = ""
    occupational_interest: float = 0


# --- Tasks ---


class Task(BaseModel):
    """Occupation task statement."""

    id: str
    title: str
    importance: float = 0
    category: str = ""


# --- Work context ---


class WorkContext(BaseModel):
    """Work context element."""

    id: str
    name: str
    description: str = ""
    category: str = ""
    score: float = 0


# --- Education ---


class Education(BaseModel):
    """Education level with respondent percentage.

    `code` is the education-level ordinal the API returns as an int, not a
    SOC code.
    """

    code: int
    title: str
    percentage_of_respondents: float = 0


# --- Job zone ---


class JobZone(BaseModel):
    """Job zone classification — how much preparation an occupation needs.

    `code` is the zone number (1-5), not a SOC code.
    """

    code: int
    title: str
    education: str = ""
    related_experience: str = ""
    job_training: str = ""
    job_zone_examples: str = ""
    svp_range: str = ""


# --- Technology ---


class TechnologyExample(BaseModel):
    """A single tool or product within a technology category."""

    title: str
    href: str = ""
    hot_technology: bool = False


class TechnologyCategory(BaseModel):
    """A UNSPSC technology category with its example tools.

    This is the API's own shape, under the payload's `category` key.
    """

    code: int
    title: str
    example: list[TechnologyExample] = Field(default_factory=list)


class TechnologySkill(BaseModel):
    """One technology, flattened out of its category for easy iteration."""

    category_code: int = 0
    category_title: str = ""
    example_name: str = ""
    hot_technology: bool = False


class HotTechnology(BaseModel):
    """Hot technology / in-demand tool."""

    title: str
    hot_technology: bool = False
    in_demand: bool = False
    percentage: float = 0


# --- Detailed work activities ---


class DetailedWorkActivity(BaseModel):
    """Detailed work activity."""

    id: str
    title: str


# --- Database tables ---


class TableRef(BaseModel):
    """Reference to a database table.

    `table_id` is the identifier `table_info()` and `table_rows()` take —
    snake_case, e.g. `essential_skills`, not `Skills`.
    """

    table_id: str
    title: str
    description: str = ""
    info: str = ""
    rows: str = ""


class TableColumn(BaseModel):
    """Column metadata for a database table.

    `column_id` is the raw column identifier used as the dict key in row data
    (after snake-case normalization). `title` is the human-readable display name.
    """

    column_id: str
    title: str
    type: str = ""
    description: str = ""
    optional: bool = False


class TableRow(BaseModel, extra="allow"):
    """A row from a database table (dynamic columns)."""


# --- Crosswalk ---


class MilitaryCrosswalk(BaseModel):
    """Military-to-civilian occupation crosswalk entry.

    `code` and `title` identify the *military* occupation (MOS, AFSC, or
    rating); `occupations` holds the civilian O*NET-SOC codes it maps to.
    The API names that nested list `occupation`, hence the alias.
    """

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    code: str
    title: str
    occupations: list[OccupationRef] = Field(default_factory=list, alias="occupation")


# --- Taxonomy ---


class TaxonomyMapping(BaseModel):
    """Taxonomy version mapping entry."""

    code: str
    title: str


# --- Interest Profiler ---


class AnswerOption(BaseModel):
    """Likert scale option for the Interest Profiler."""

    value: int
    name: str


class ProfilerQuestion(BaseModel):
    """A single Interest Profiler item."""

    index: int
    area: str
    text: str


class ProfilerQuestions(BaseModel):
    """The full Interest Profiler question set with answer options."""

    total: int
    answer_options: list[AnswerOption] = Field(default_factory=list)
    questions: list[ProfilerQuestion] = Field(default_factory=list)


class ProfilerResult(BaseModel):
    """RIASEC dimension score from the Interest Profiler."""

    code: str
    title: str
    description: str = ""
    score: int = 0


class ProfilerCareer(BaseModel):
    """Career match from the Interest Profiler."""

    code: str
    title: str
    fit: str = ""
    href: str = ""


# --- Computed analysis results ---


class SkillGapItem(BaseModel):
    """A single element where the target occupation scores higher than the source."""

    name: str
    section: str
    from_score: float
    to_score: float
    gap: float


class SkillGapResult(BaseModel):
    """Full skill gap analysis between two occupations."""

    from_code: str
    from_title: str
    to_code: str
    to_title: str
    gaps: list[SkillGapItem] = Field(default_factory=list)
    strengths: list[SkillGapItem] = Field(default_factory=list)


class SimilarityBreakdown(BaseModel):
    """Per-domain similarity scores."""

    knowledge: float = 0.0
    skills: float = 0.0
    abilities: float = 0.0
    work_styles: float = 0.0
    interests: float = 0.0


class SimilarityResult(BaseModel):
    """Cosine similarity between two occupation profiles."""

    code_a: str
    code_b: str
    overall: float = 0.0
    breakdown: SimilarityBreakdown = Field(default_factory=SimilarityBreakdown)


class RiasecFitResult(BaseModel):
    """Fit score between a person's RIASEC profile and an occupation."""

    code: str
    title: str
    score: float = 0.0
    fit: str = ""
    person_profile: dict[str, float] = Field(default_factory=dict)
    occupation_profile: dict[str, float] = Field(default_factory=dict)


# --- Bundled KSAO + RIASEC output ---


class OccupationProfile(BaseModel):
    """Full KSAO + RIASEC profile for an occupation."""

    code: str
    title: str
    description: str = ""
    interests: list[Interest] = Field(default_factory=list)
    knowledge: list[ScoredElement] = Field(default_factory=list)
    skills: list[ScoredElement] = Field(default_factory=list)
    abilities: list[ScoredElement] = Field(default_factory=list)
    work_styles: list[ScoredElement] = Field(default_factory=list)

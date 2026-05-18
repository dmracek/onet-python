"""Pydantic response models for O*NET Web Services API v2."""

from __future__ import annotations

from pydantic import BaseModel, Field

# --- Pagination ---


class PaginatedResponse[T](BaseModel):
    """Generic paginated response wrapper."""

    start: int = 1
    end: int = 0
    total: int = 0
    items: list[T] = Field(default_factory=list)


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
    """Education level with respondent percentage."""

    code: str
    title: str
    percentage_of_respondents: float = 0


# --- Job zone ---


class JobZone(BaseModel):
    """Job zone classification."""

    code: str
    title: str
    education: str = ""
    experience: str = ""
    job_training: str = ""
    job_zone: int = 0
    svp_range: str = ""


# --- Technology ---


class TechnologySkill(BaseModel):
    """Technology skill with category info."""

    category_code: str = ""
    category_title: str = ""
    example_name: str = ""
    hot_technology: bool = False
    in_demand: bool = False


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
    """Reference to a database table."""

    id: str
    title: str


class TableColumn(BaseModel):
    """Column metadata for a database table."""

    name: str
    type: str
    description: str = ""


class TableRow(BaseModel, extra="allow"):
    """A row from a database table (dynamic columns)."""


# --- Crosswalk ---


class MilitaryCrosswalk(BaseModel):
    """Military-to-civilian occupation crosswalk entry."""

    code: str
    title: str


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

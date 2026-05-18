"""Tests for computed analysis methods — skill_gap, profile_similarity, riasec_fit, to_dataframe."""

from __future__ import annotations

import pytest

from onet.client import OnetClient
from onet.models import (
    Interest,
    OccupationDetail,
    OccupationProfile,
    RiasecFitResult,
    ScoredElement,
    SimilarityResult,
    SkillGapResult,
)

from .conftest import StubTransport

# ---------------------------------------------------------------------------
# Fixtures — two distinct occupation profiles for comparison
# ---------------------------------------------------------------------------

TEACHER_PROFILE = OccupationProfile(
    code="25-2021.00",
    title="Elementary School Teachers",
    description="Teach.",
    interests=[
        Interest(id="1", name="Social", occupational_interest=100),
        Interest(id="2", name="Artistic", occupational_interest=48),
        Interest(id="3", name="Investigative", occupational_interest=39),
        Interest(id="4", name="Conventional", occupational_interest=46),
        Interest(id="5", name="Realistic", occupational_interest=27),
        Interest(id="6", name="Enterprising", occupational_interest=26),
    ],
    knowledge=[
        ScoredElement(id="k1", name="English Language", importance=97),
        ScoredElement(id="k2", name="Education and Training", importance=96),
        ScoredElement(id="k3", name="Mathematics", importance=73),
        ScoredElement(id="k4", name="Psychology", importance=67),
    ],
    skills=[
        ScoredElement(id="s1", name="Instructing", importance=81),
        ScoredElement(id="s2", name="Speaking", importance=78),
        ScoredElement(id="s3", name="Active Listening", importance=75),
        ScoredElement(id="s4", name="Critical Thinking", importance=75),
    ],
    abilities=[
        ScoredElement(id="a1", name="Oral Expression", importance=91),
        ScoredElement(id="a2", name="Oral Comprehension", importance=75),
    ],
    work_styles=[
        ScoredElement(id="w1", name="Dependability", importance=88),
        ScoredElement(id="w2", name="Cooperation", importance=85),
        ScoredElement(id="w3", name="Empathy", importance=85),
    ],
)

ZOOLOGIST_PROFILE = OccupationProfile(
    code="19-1023.00",
    title="Zoologists and Wildlife Biologists",
    description="Study animals.",
    interests=[
        Interest(id="1", name="Investigative", occupational_interest=100),
        Interest(id="2", name="Realistic", occupational_interest=74),
        Interest(id="3", name="Conventional", occupational_interest=45),
        Interest(id="4", name="Social", occupational_interest=26),
        Interest(id="5", name="Artistic", occupational_interest=22),
        Interest(id="6", name="Enterprising", occupational_interest=22),
    ],
    knowledge=[
        ScoredElement(id="k1", name="Biology", importance=95),
        ScoredElement(id="k2", name="English Language", importance=69),
        ScoredElement(id="k3", name="Mathematics", importance=60),
        ScoredElement(id="k4", name="Geography", importance=59),
    ],
    skills=[
        ScoredElement(id="s1", name="Science", importance=72),
        ScoredElement(id="s2", name="Speaking", importance=75),
        ScoredElement(id="s3", name="Active Listening", importance=75),
        ScoredElement(id="s4", name="Critical Thinking", importance=75),
    ],
    abilities=[
        ScoredElement(id="a1", name="Oral Expression", importance=75),
        ScoredElement(id="a2", name="Oral Comprehension", importance=75),
        ScoredElement(id="a3", name="Inductive Reasoning", importance=75),
    ],
    work_styles=[
        ScoredElement(id="w1", name="Intellectual Curiosity", importance=88),
        ScoredElement(id="w2", name="Dependability", importance=77),
        ScoredElement(id="w3", name="Attention to Detail", importance=73),
    ],
)


_FIXTURE_PROFILES: dict[str, OccupationProfile] = {
    "25-2021.00": TEACHER_PROFILE,
    "19-1023.00": ZOOLOGIST_PROFILE,
}


@pytest.fixture
def analysis_client(monkeypatch: pytest.MonkeyPatch) -> OnetClient:
    """Client whose profile/occupation/interests methods return canned fixtures."""
    client = OnetClient(api_key="test", transport=StubTransport())

    def fake_profile(self: OnetClient, code: str) -> OccupationProfile:
        return _FIXTURE_PROFILES[code]

    def fake_occupation(self: OnetClient, code: str) -> OccupationDetail:
        p = _FIXTURE_PROFILES[code]
        return OccupationDetail(code=p.code, title=p.title, description=p.description)

    def fake_interests(self: OnetClient, code: str) -> list[Interest]:
        return _FIXTURE_PROFILES[code].interests

    monkeypatch.setattr(OnetClient, "occupation_profile", fake_profile)
    monkeypatch.setattr(OnetClient, "occupation", fake_occupation)
    monkeypatch.setattr(OnetClient, "interests", fake_interests)
    return client


# ---------------------------------------------------------------------------
# _cosine_similarity (static method)
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        assert OnetClient._cosine_similarity([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        assert OnetClient._cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_opposite_vectors(self) -> None:
        assert OnetClient._cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self) -> None:
        assert OnetClient._cosine_similarity([0, 0, 0], [1, 2, 3]) == 0.0

    def test_both_zero_returns_zero(self) -> None:
        assert OnetClient._cosine_similarity([0, 0], [0, 0]) == 0.0

    @pytest.mark.parametrize(
        "a, b, expected",
        [
            pytest.param([3, 4], [4, 3], 0.96, id="similar-vectors"),
            pytest.param([1, 1, 1], [1, 1, 1], 1.0, id="uniform-identical"),
            pytest.param([100], [50], 1.0, id="scalar-same-direction"),
        ],
    )
    def test_known_values(self, a: list[float], b: list[float], expected: float) -> None:
        assert OnetClient._cosine_similarity(a, b) == pytest.approx(expected, abs=0.01)


# ---------------------------------------------------------------------------
# skill_gap
# ---------------------------------------------------------------------------


class TestSkillGap:
    def test_returns_skill_gap_result(self, analysis_client: OnetClient) -> None:
        result = analysis_client.skill_gap("25-2021.00", "19-1023.00")
        assert isinstance(result, SkillGapResult)
        assert result.from_code == "25-2021.00"
        assert result.to_code == "19-1023.00"
        assert result.from_title == "Elementary School Teachers"
        assert result.to_title == "Zoologists and Wildlife Biologists"

    def test_gaps_are_sorted_by_magnitude(self, analysis_client: OnetClient) -> None:
        result = analysis_client.skill_gap("25-2021.00", "19-1023.00")
        gap_values = [g.gap for g in result.gaps]
        assert gap_values == sorted(gap_values, reverse=True)

    def test_strengths_are_sorted_by_magnitude(self, analysis_client: OnetClient) -> None:
        result = analysis_client.skill_gap("25-2021.00", "19-1023.00")
        str_values = [s.gap for s in result.strengths]
        assert str_values == sorted(str_values, reverse=True)

    def test_biology_is_a_gap(self, analysis_client: OnetClient) -> None:
        """Teacher → Zoologist: Biology (0 → 95) should be the largest gap."""
        result = analysis_client.skill_gap("25-2021.00", "19-1023.00")
        biology_gaps = [g for g in result.gaps if g.name == "Biology"]
        assert len(biology_gaps) == 1
        assert biology_gaps[0].gap == 95
        assert biology_gaps[0].section == "knowledge"
        assert biology_gaps[0].from_score == 0
        assert biology_gaps[0].to_score == 95

    def test_education_is_a_strength(self, analysis_client: OnetClient) -> None:
        """Teacher → Zoologist: Education and Training (96 → 0) is a strength."""
        result = analysis_client.skill_gap("25-2021.00", "19-1023.00")
        edu_strengths = [s for s in result.strengths if s.name == "Education and Training"]
        assert len(edu_strengths) == 1
        assert edu_strengths[0].gap == 96

    def test_equal_scores_in_neither(self, analysis_client: OnetClient) -> None:
        """Elements where both occupations score identically appear in neither list."""
        result = analysis_client.skill_gap("25-2021.00", "19-1023.00")
        all_names = {g.name for g in result.gaps} | {s.name for s in result.strengths}
        # Active Listening is 75 for both — should not appear
        assert "Active Listening" not in all_names

    def test_identical_occupations_empty(self, analysis_client: OnetClient) -> None:
        """Comparing an occupation with itself produces no gaps or strengths."""
        result = analysis_client.skill_gap("25-2021.00", "25-2021.00")
        assert result.gaps == []
        assert result.strengths == []


# ---------------------------------------------------------------------------
# profile_similarity
# ---------------------------------------------------------------------------


class TestProfileSimilarity:
    def test_returns_similarity_result(self, analysis_client: OnetClient) -> None:
        result = analysis_client.profile_similarity("25-2021.00", "19-1023.00")
        assert isinstance(result, SimilarityResult)
        assert result.code_a == "25-2021.00"
        assert result.code_b == "19-1023.00"

    def test_overall_between_zero_and_one(self, analysis_client: OnetClient) -> None:
        result = analysis_client.profile_similarity("25-2021.00", "19-1023.00")
        assert 0.0 <= result.overall <= 1.0

    def test_self_similarity_is_one(self, analysis_client: OnetClient) -> None:
        result = analysis_client.profile_similarity("25-2021.00", "25-2021.00")
        assert result.overall == pytest.approx(1.0)

    def test_breakdown_has_all_domains(self, analysis_client: OnetClient) -> None:
        result = analysis_client.profile_similarity("25-2021.00", "19-1023.00")
        bd = result.breakdown
        for domain in ("knowledge", "skills", "abilities", "work_styles", "interests"):
            score = getattr(bd, domain)
            assert 0.0 <= score <= 1.0, f"{domain} out of range: {score}"

    def test_skills_more_similar_than_knowledge(self, analysis_client: OnetClient) -> None:
        """Teacher/Zoologist share Speaking, Active Listening, Critical Thinking
        but have very different knowledge domains."""
        result = analysis_client.profile_similarity("25-2021.00", "19-1023.00")
        assert result.breakdown.skills > result.breakdown.knowledge


# ---------------------------------------------------------------------------
# riasec_fit
# ---------------------------------------------------------------------------


class TestRiasecFit:
    def test_returns_fit_result(self, analysis_client: OnetClient) -> None:
        scores = {"S": 100, "A": 50, "I": 40, "C": 40, "R": 25, "E": 25}
        # Patch interests and occupation for direct call
        result = analysis_client.riasec_fit(scores, "25-2021.00")
        assert isinstance(result, RiasecFitResult)
        assert result.code == "25-2021.00"

    def test_strong_fit_for_matching_profile(self, analysis_client: OnetClient) -> None:
        """A Social-dominant person should be a strong fit for teaching."""
        scores = {"S": 100, "A": 48, "I": 39, "C": 46, "R": 27, "E": 26}
        result = analysis_client.riasec_fit(scores, "25-2021.00")
        assert result.fit == "strong"
        assert result.score >= 0.85

    def test_weak_fit_for_opposite_profile(self, analysis_client: OnetClient) -> None:
        """A Realistic-dominant person should be a weak/moderate fit for teaching."""
        scores = {"R": 100, "C": 80, "E": 70, "I": 10, "A": 5, "S": 5}
        result = analysis_client.riasec_fit(scores, "25-2021.00")
        assert result.fit in ("weak", "moderate")
        assert result.score < 0.65

    @pytest.mark.parametrize(
        "key_format",
        [
            pytest.param(
                {"R": 50, "I": 50, "A": 50, "S": 50, "E": 50, "C": 50}, id="single-letter"
            ),
            pytest.param(
                {
                    "Realistic": 50,
                    "Investigative": 50,
                    "Artistic": 50,
                    "Social": 50,
                    "Enterprising": 50,
                    "Conventional": 50,
                },
                id="full-name",
            ),
            pytest.param(
                {
                    "realistic": 50,
                    "investigative": 50,
                    "artistic": 50,
                    "social": 50,
                    "enterprising": 50,
                    "conventional": 50,
                },
                id="lowercase",
            ),
        ],
    )
    def test_accepts_multiple_key_formats(
        self, analysis_client: OnetClient, key_format: dict[str, float]
    ) -> None:
        result = analysis_client.riasec_fit(key_format, "25-2021.00")
        assert result.score > 0

    def test_profiles_included_in_result(self, analysis_client: OnetClient) -> None:
        scores = {"S": 80, "I": 60, "A": 40, "C": 30, "R": 20, "E": 10}
        result = analysis_client.riasec_fit(scores, "25-2021.00")
        assert result.person_profile["Social"] == 80
        assert result.occupation_profile["Social"] == 100

    def test_empty_person_scores_raises(self, analysis_client: OnetClient) -> None:
        with pytest.raises(ValueError, match="at least one RIASEC dimension"):
            analysis_client.riasec_fit({}, "25-2021.00")

    def test_all_unrecognized_keys_raises(self, analysis_client: OnetClient) -> None:
        with pytest.raises(ValueError, match="No recognized RIASEC keys"):
            analysis_client.riasec_fit({"foo": 1.0, "bar": 2.0}, "25-2021.00")


# ---------------------------------------------------------------------------
# to_dataframe
# ---------------------------------------------------------------------------


class TestToDataframe:
    def test_returns_dataframe(self, analysis_client: OnetClient) -> None:
        pd = pytest.importorskip("pandas")
        df = analysis_client.to_dataframe(["25-2021.00"])
        assert isinstance(df, pd.DataFrame)

    def test_shape(self, analysis_client: OnetClient) -> None:
        pytest.importorskip("pandas")
        df = analysis_client.to_dataframe(["25-2021.00", "19-1023.00"])
        assert len(df) == 2
        assert "code" in df.columns
        assert "title" in df.columns

    def test_columns_are_prefixed(self, analysis_client: OnetClient) -> None:
        pytest.importorskip("pandas")
        df = analysis_client.to_dataframe(["25-2021.00"])
        ksao_cols = [c for c in df.columns if c not in ("code", "title")]
        prefixes = {c.split("_")[0] for c in ksao_cols}
        assert prefixes == {"knowledge", "skills", "abilities", "work", "interest"}

    def test_no_nulls(self, analysis_client: OnetClient) -> None:
        """Missing elements for one occupation should be filled with 0.0."""
        pytest.importorskip("pandas")
        df = analysis_client.to_dataframe(["25-2021.00", "19-1023.00"])
        assert df.isna().sum().sum() == 0

    def test_filter_sections(self, analysis_client: OnetClient) -> None:
        pytest.importorskip("pandas")
        df = analysis_client.to_dataframe(["25-2021.00"], sections=["knowledge"])
        ksao_cols = [c for c in df.columns if c not in ("code", "title")]
        assert all(c.startswith("knowledge_") for c in ksao_cols)

    def test_unknown_section_raises(self, analysis_client: OnetClient) -> None:
        pytest.importorskip("pandas")
        with pytest.raises(ValueError, match="Unknown sections"):
            analysis_client.to_dataframe(["25-2021.00"], sections=["work_style"])

    def test_values_are_correct(self, analysis_client: OnetClient) -> None:
        pytest.importorskip("pandas")
        df = analysis_client.to_dataframe(["25-2021.00"], sections=["knowledge"])
        row = df.iloc[0]
        assert row["knowledge_english_language"] == 97
        assert row["knowledge_education_and_training"] == 96

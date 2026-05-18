"""O*NET Web Services API v2 client.

Usage::

    from onet import OnetClient

    with OnetClient() as onet:
        results = onet.search("marine biologist")
        profile = onet.occupation_profile(results[0].code)
"""

from onet.client import OnetClient
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

__all__ = [
    "OnetClient",
    "AnswerOption",
    "DetailedWorkActivity",
    "Education",
    "HotTechnology",
    "Interest",
    "JobZone",
    "MilitaryCrosswalk",
    "OccupationDetail",
    "OccupationProfile",
    "OccupationRef",
    "ProfilerCareer",
    "ProfilerQuestion",
    "ProfilerQuestions",
    "ProfilerResult",
    "RiasecFitResult",
    "ScoredElement",
    "SimilarityBreakdown",
    "SimilarityResult",
    "SkillGapItem",
    "SkillGapResult",
    "TableColumn",
    "TableRef",
    "Task",
    "TaxonomyMapping",
    "TechnologySkill",
    "WorkContext",
]

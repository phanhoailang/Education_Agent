from dataclasses import dataclass
from typing import List
from modules.rag_module.datatypes.CoverageLevel import CoverageLevel

@dataclass
class CoverageAssessment:
    """Data class for coverage assessment results"""
    level: CoverageLevel
    score: float
    missing_topics: List[str]
    covered_topics: List[str]
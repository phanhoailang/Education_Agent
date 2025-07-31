from enum import Enum

class CoverageLevel(Enum):
    """Enum for coverage assessment levels"""
    INSUFFICIENT = "insufficient"
    PARTIAL = "partial"
    ADEQUATE = "adequate"
    COMPREHENSIVE = "comprehensive"

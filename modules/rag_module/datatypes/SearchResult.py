from dataclasses import dataclass
from typing import Dict

@dataclass
class SearchResult:
    title: str
    snippet: str
    url: str
    metadata: Dict = None
    score: float = 0.0
    llm_reasoning: str = ""
    final_rank: int = 0
    strengths: Dict = None
    detailed_scores: Dict = None
    snippet_analysis: str = ""
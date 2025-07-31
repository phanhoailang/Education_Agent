from dataclasses import dataclass
from typing import Optional

@dataclass
class QueryResult:
    chunk_id: str
    content: str
    score: float
    source_file: str
    page_number: Optional[int] = None
    subtopic: Optional[str] = None
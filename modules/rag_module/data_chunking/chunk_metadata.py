from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
import hashlib

@dataclass
class ChunkMetadata:
    """
    Metadata cho mỗi chunk văn bản tiếng Việt (simplified version).
    Chứa thông tin cần thiết cho việc retrieval, bỏ source info và named entities.
    """
    
    # Thông tin cơ bản
    chunk_id: str = field(default_factory=lambda: "")
    chunk_index: int = 0
    
    # Nội dung và vị trí
    content: str = ""
    char_start: int = 0
    char_end: int = 0
    char_count: int = 0
    word_count: int = 0
    sentence_count: int = 0
    
    # Thông tin chunking
    chunking_strategy: str = ""
    chunk_overlap_prev: int = 0
    chunk_overlap_next: int = 0
    
    # Thông tin ngôn ngữ tiếng Việt
    vietnamese_features: Dict[str, Any] = field(default_factory=dict)
    pos_tags: List[str] = field(default_factory=list)
    
    # Điểm chất lượng
    semantic_coherence_score: Optional[float] = None
    completeness_score: Optional[float] = None
    
    # Metadata bổ sung
    keywords: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    language_confidence: float = 1.0
    
    # Thông tin kỹ thuật
    processing_time: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    hash_content: str = field(default="")
    
    def __post_init__(self):
        """Tự động tính toán các giá trị sau khi khởi tạo."""
        if not self.chunk_id:
            self.chunk_id = self._generate_chunk_id()
        
        if not self.hash_content and self.content:
            self.hash_content = self._calculate_content_hash()
        
        if self.content and not self.char_count:
            self.char_count = len(self.content)
            self.word_count = len(self.content.split())
            self.sentence_count = self.content.count('.') + self.content.count('!') + self.content.count('?')
    
    def _generate_chunk_id(self) -> str:
        """Tạo ID duy nhất cho chunk."""
        timestamp = int(self.created_at.timestamp() * 1000)
        content_hash = hashlib.md5(self.content.encode()).hexdigest()[:8]
        return f"chunk_{content_hash}_{self.chunk_index}_{timestamp}"
    
    def _calculate_content_hash(self) -> str:
        """Tính hash của nội dung để tracking thay đổi."""
        return hashlib.sha256(self.content.encode('utf-8')).hexdigest()[:16]
    
    def add_vietnamese_feature(self, feature_name: str, feature_value: Any):
        """Thêm đặc điểm ngôn ngữ tiếng Việt."""
        self.vietnamese_features[feature_name] = feature_value
    
    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi thành dictionary để lưu trữ (simplified)."""
        return {
            'chunk_id': self.chunk_id,
            'chunk_index': self.chunk_index,
            'content': self.content,
            'char_start': self.char_start,
            'char_end': self.char_end,
            'char_count': self.char_count,
            'word_count': self.word_count,
            'sentence_count': self.sentence_count,
            'chunking_strategy': self.chunking_strategy,
            'chunk_overlap_prev': self.chunk_overlap_prev,
            'chunk_overlap_next': self.chunk_overlap_next,
            'vietnamese_features': self.vietnamese_features,
            'pos_tags': self.pos_tags,
            'semantic_coherence_score': self.semantic_coherence_score,
            'completeness_score': self.completeness_score,
            'keywords': self.keywords,
            'topics': self.topics,
            'language_confidence': self.language_confidence,
            'processing_time': self.processing_time,
            'created_at': self.created_at.isoformat(),
            'hash_content': self.hash_content
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChunkMetadata':
        """Tạo ChunkMetadata từ dictionary."""
        # Convert created_at từ string về datetime
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        
        return cls(**data)
    
    def get_summary(self) -> str:
        """Trả về tóm tắt thông tin chunk."""
        return (
            f"Chunk {self.chunk_id}: {self.char_count} chars, "
            f"{self.word_count} words, {self.sentence_count} sentences, "
            f"Strategy: {self.chunking_strategy}"
        )
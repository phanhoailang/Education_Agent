from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import re
import logging
from dataclasses import dataclass

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logging.warning("LangChain text splitters not available. Using fallback implementations.")

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning("SentenceTransformers not available. Semantic chunking will be limited.")

@dataclass
class ChunkResult:
    """Kết quả chunking."""
    content: str
    start_index: int
    end_index: int
    chunk_type: str = "content"
    confidence_score: float = 1.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class ChunkingStrategy(ABC):
    """Base class cho các chiến lược chunking."""
    
    def __init__(self, name: str, **kwargs):
        self.name = name
        self.params = kwargs
    
    @abstractmethod
    def split_text(self, text: str, **kwargs) -> List[ChunkResult]:
        """Tách văn bản thành các chunks."""
        pass
    
    def get_optimal_chunk_size(self, text: str) -> int:
        """Tính toán kích thước chunk tối ưu dựa trên văn bản."""
        # Default implementation
        text_length = len(text)
        if text_length < 1000:
            return 200
        elif text_length < 5000:
            return 500
        elif text_length < 20000:
            return 1000
        else:
            return 1500

class FixedSizeStrategy(ChunkingStrategy):
    """Chiến lược chia theo kích thước cố định."""
    
    def __init__(self, chunk_size: int = 1000, overlap: int = 200, **kwargs):
        super().__init__("fixed_size", **kwargs)
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def split_text(self, text: str, **kwargs) -> List[ChunkResult]:
        """Chia văn bản theo kích thước cố định với overlap."""
        if not text:
            return []
        
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            
            # Tìm điểm cắt tốt hơn gần cuối chunk
            if end < len(text):
                # Tìm khoảng trắng gần nhất
                for i in range(end, max(end - 100, start), -1):
                    if text[i].isspace():
                        end = i
                        break
            
            chunk_content = text[start:end].strip()
            if chunk_content:
                chunk = ChunkResult(
                    content=chunk_content,
                    start_index=start,
                    end_index=end,
                    chunk_type="fixed_size",
                    metadata={
                        'chunk_index': chunk_index,
                        'chunk_size': len(chunk_content),
                        'overlap_size': self.overlap if chunk_index > 0 else 0
                    }
                )
                chunks.append(chunk)
                chunk_index += 1
            
            # Di chuyển start với overlap
            start = max(start + self.chunk_size - self.overlap, end)
            if start >= len(text):
                break
        
        return chunks

class SentenceAwareStrategy(ChunkingStrategy):
    """Chiến lược chia theo câu, tôn trọng cấu trúc câu tiếng Việt."""
    
    def __init__(self, target_size: int = 1000, max_sentences: int = 10, 
                 min_chunk_size: int = 100, **kwargs):
        super().__init__("sentence_aware", **kwargs)
        self.target_size = target_size
        self.max_sentences = max_sentences
        self.min_chunk_size = min_chunk_size
        
        # Patterns cho tách câu tiếng Việt
        self.sentence_pattern = re.compile(
            r'(?<=[.!?])\s+(?=[A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ])'
        )
        
        # Danh sách viết tắt tiếng Việt
        self.abbreviations = {
            'TP.', 'ThS.', 'PGS.', 'GS.', 'TS.', 'BS.', 'KS.', 'CN.',
            'Th.', 'Q.', 'P.', 'TT.', 'HCM.', 'SG.', 'HN.', 'Tp.',
            'vs.', 'VD.', 'NXB.', 'TPHCM.', 'ĐHQG.', 'PGĐ.'
        }
    
    def split_text(self, text: str, **kwargs) -> List[ChunkResult]:
        """Chia văn bản theo câu với kích thước mục tiêu."""
        sentences = self._split_sentences(text)
        if not sentences:
            return []
        
        chunks = []
        current_chunk = []
        current_size = 0
        start_index = 0
        
        for i, sentence in enumerate(sentences):
            sentence_size = len(sentence)
            
            # Kiểm tra nếu thêm câu này vào chunk hiện tại
            if (current_size + sentence_size <= self.target_size and 
                len(current_chunk) < self.max_sentences):
                current_chunk.append(sentence)
                current_size += sentence_size
            else:
                # Tạo chunk từ các câu hiện tại
                if current_chunk and current_size >= self.min_chunk_size:
                    chunk_content = ' '.join(current_chunk)
                    end_index = start_index + len(chunk_content)
                    
                    chunk = ChunkResult(
                        content=chunk_content,
                        start_index=start_index,
                        end_index=end_index,
                        chunk_type="sentence_aware",
                        metadata={
                            'sentence_count': len(current_chunk),
                            'avg_sentence_length': current_size / len(current_chunk)
                        }
                    )
                    chunks.append(chunk)
                    start_index = end_index + 1
                
                # Bắt đầu chunk mới
                current_chunk = [sentence]
                current_size = sentence_size
        
        # Xử lý chunk cuối cùng
        if current_chunk:
            chunk_content = ' '.join(current_chunk)
            chunk = ChunkResult(
                content=chunk_content,
                start_index=start_index,
                end_index=start_index + len(chunk_content),
                chunk_type="sentence_aware",
                metadata={
                    'sentence_count': len(current_chunk),
                    'avg_sentence_length': current_size / len(current_chunk) if current_chunk else 0
                }
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_sentences(self, text: str) -> List[str]:
        """Tách câu tiếng Việt chính xác."""
        # Preprocessing: Bảo vệ các viết tắt
        protected_text = text
        for abbr in self.abbreviations:
            protected_text = protected_text.replace(abbr, abbr.replace('.', '<DOT>'))
        
        # Tách câu
        sentences = re.split(self.sentence_pattern, protected_text)
        
        # Khôi phục dấu chấm trong viết tắt
        sentences = [s.replace('<DOT>', '.').strip() for s in sentences if s.strip()]
        
        return sentences

class SemanticStrategy(ChunkingStrategy):
    """Chiến lược chia theo ngữ nghĩa sử dụng sentence embeddings."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", 
                 similarity_threshold: float = 0.7,
                 target_size: int = 1000,
                 max_chunk_size: int = 1500, **kwargs):
        super().__init__("semantic", **kwargs)
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self.target_size = target_size
        self.max_chunk_size = max_chunk_size
        self.model = None
        
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.model = SentenceTransformer(model_name)
            except Exception as e:
                logging.error(f"Failed to load SentenceTransformer model: {e}")
                self.model = None
        
    def split_text(self, text: str, **kwargs) -> List[ChunkResult]:
        """Chia văn bản theo ngữ nghĩa."""
        if not self.model:
            logging.warning("SentenceTransformer model not available. Falling back to sentence-aware strategy.")
            fallback = SentenceAwareStrategy(target_size=self.target_size)
            return fallback.split_text(text, **kwargs)
        
        # Tách câu
        sentence_strategy = SentenceAwareStrategy()
        sentences = sentence_strategy._split_sentences(text)
        
        if len(sentences) <= 1:
            return [ChunkResult(
                content=text,
                start_index=0,
                end_index=len(text),
                chunk_type="semantic"
            )]
        
        # Tính embeddings cho các câu
        try:
            embeddings = self.model.encode(sentences)
        except Exception as e:
            logging.error(f"Failed to encode sentences: {e}")
            fallback = SentenceAwareStrategy(target_size=self.target_size)
            return fallback.split_text(text, **kwargs)
        
        # Tìm breakpoints dựa trên độ tương tự ngữ nghĩa
        breakpoints = self._find_semantic_breakpoints(embeddings, sentences)
        
        # Tạo chunks từ breakpoints
        chunks = self._create_chunks_from_breakpoints(sentences, breakpoints, text)
        
        return chunks
    
    def _find_semantic_breakpoints(self, embeddings: np.ndarray, 
                                  sentences: List[str]) -> List[int]:
        """Tìm điểm cắt dựa trên thay đổi ngữ nghĩa."""
        breakpoints = [0]  # Bắt đầu luôn là breakpoint
        
        for i in range(1, len(embeddings)):
            # Tính độ tương tự với câu trước
            similarity = cosine_similarity(
                embeddings[i-1:i], embeddings[i:i+1]
            )[0][0]
            
            # Tính độ tương tự trung bình với vài câu trước đó
            if i >= 3:
                window_similarities = []
                for j in range(max(0, i-3), i):
                    sim = cosine_similarity(
                        embeddings[j:j+1], embeddings[i:i+1]
                    )[0][0]
                    window_similarities.append(sim)
                avg_similarity = np.mean(window_similarities)
            else:
                avg_similarity = similarity
            
            # Nếu độ tương tự thấp hơn threshold, đây là breakpoint
            if avg_similarity < self.similarity_threshold:
                breakpoints.append(i)
        
        breakpoints.append(len(sentences))  # Kết thúc luôn là breakpoint
        return breakpoints
    
    def _create_chunks_from_breakpoints(self, sentences: List[str], 
                                       breakpoints: List[int],
                                       original_text: str) -> List[ChunkResult]:
        """Tạo chunks từ các breakpoints."""
        chunks = []
        
        for i in range(len(breakpoints) - 1):
            start_idx = breakpoints[i]
            end_idx = breakpoints[i + 1]
            
            chunk_sentences = sentences[start_idx:end_idx]
            chunk_content = ' '.join(chunk_sentences)
            
            # Kiểm tra kích thước chunk
            if len(chunk_content) > self.max_chunk_size:
                # Chia nhỏ chunk lớn
                sub_chunks = self._split_large_chunk(chunk_sentences)
                chunks.extend(sub_chunks)
            elif len(chunk_content.strip()) > 0:
                # Tìm vị trí trong văn bản gốc
                start_pos = original_text.find(chunk_sentences[0])
                if start_pos == -1:
                    start_pos = 0
                
                chunk = ChunkResult(
                    content=chunk_content,
                    start_index=start_pos,
                    end_index=start_pos + len(chunk_content),
                    chunk_type="semantic",
                    metadata={
                        'sentence_count': len(chunk_sentences),
                        'semantic_coherence': True
                    }
                )
                chunks.append(chunk)
        
        return chunks
    
    def _split_large_chunk(self, sentences: List[str]) -> List[ChunkResult]:
        """Chia chunk lớn thành các chunk nhỏ hơn."""
        chunks = []
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            if current_size + len(sentence) <= self.target_size:
                current_chunk.append(sentence)
                current_size += len(sentence)
            else:
                if current_chunk:
                    chunk_content = ' '.join(current_chunk)
                    chunk = ChunkResult(
                        content=chunk_content,
                        start_index=0,  # Will be updated later
                        end_index=len(chunk_content),
                        chunk_type="semantic_split",
                        metadata={'sentence_count': len(current_chunk)}
                    )
                    chunks.append(chunk)
                
                current_chunk = [sentence]
                current_size = len(sentence)
        
        if current_chunk:
            chunk_content = ' '.join(current_chunk)
            chunk = ChunkResult(
                content=chunk_content,
                start_index=0,
                end_index=len(chunk_content),
                chunk_type="semantic_split",
                metadata={'sentence_count': len(current_chunk)}
            )
            chunks.append(chunk)
        
        return chunks

class RecursiveStrategy(ChunkingStrategy):
    """Chiến lược chia đệ quy sử dụng LangChain RecursiveCharacterTextSplitter."""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200,
                 vietnamese_separators: bool = True, **kwargs):
        super().__init__("recursive", **kwargs)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.vietnamese_separators = vietnamese_separators
        
        # Separators tối ưu cho tiếng Việt
        if vietnamese_separators:
            self.separators = [
                "\n\n",  # Paragraph breaks
                "\n",    # Line breaks
                ". ",    # Sentence endings with space
                "! ",    # Exclamation with space
                "? ",    # Question with space
                "; ",    # Semicolon with space
                ", ",    # Comma with space
                " ",     # Word breaks
                ""       # Character level
            ]
        else:
            self.separators = ["\n\n", "\n", " ", ""]
        
        self.splitter = None
        if LANGCHAIN_AVAILABLE:
            try:
                self.splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    separators=self.separators,
                    length_function=len,
                    is_separator_regex=False
                )
            except Exception as e:
                logging.error(f"Failed to initialize LangChain splitter: {e}")
                self.splitter = None
    
    def split_text(self, text: str, **kwargs) -> List[ChunkResult]:
        """Chia văn bản sử dụng recursive splitting."""
        if self.splitter:
            try:
                # Sử dụng LangChain splitter
                chunks_text = self.splitter.split_text(text)
                chunks = []
                start_idx = 0
                
                for i, chunk_content in enumerate(chunks_text):
                    # Tìm vị trí chunk trong văn bản gốc
                    chunk_start = text.find(chunk_content, start_idx)
                    if chunk_start == -1:
                        chunk_start = start_idx
                    
                    chunk = ChunkResult(
                        content=chunk_content,
                        start_index=chunk_start,
                        end_index=chunk_start + len(chunk_content),
                        chunk_type="recursive",
                        metadata={
                            'chunk_index': i,
                            'overlap_size': self.chunk_overlap if i > 0 else 0
                        }
                    )
                    chunks.append(chunk)
                    start_idx = chunk_start + len(chunk_content) - self.chunk_overlap
                
                return chunks
                
            except Exception as e:
                logging.error(f"LangChain recursive splitting failed: {e}")
        
        # Fallback implementation
        return self._fallback_recursive_split(text)
    
    def _fallback_recursive_split(self, text: str) -> List[ChunkResult]:
        """Fallback recursive splitting implementation."""
        def split_by_separator(text: str, separator: str) -> List[str]:
            if separator == "":
                # Character level split
                return list(text)
            return text.split(separator)
        
        def recursive_split(text: str, separators: List[str]) -> List[str]:
            if not separators or len(text) <= self.chunk_size:
                return [text] if text.strip() else []
            
            separator = separators[0]
            remaining_separators = separators[1:]
            
            splits = split_by_separator(text, separator)
            final_chunks = []
            
            for split in splits:
                if len(split) <= self.chunk_size:
                    if split.strip():
                        final_chunks.append(split)
                else:
                    # Recursively split large pieces
                    sub_chunks = recursive_split(split, remaining_separators)
                    final_chunks.extend(sub_chunks)
            
            return final_chunks
        
        raw_chunks = recursive_split(text, self.separators)
        
        # Merge small chunks and add overlap
        chunks = []
        i = 0
        start_idx = 0
        
        while i < len(raw_chunks):
            current_chunk = raw_chunks[i]
            current_size = len(current_chunk)
            
            # Try to merge with next chunks if current is too small
            while (i + 1 < len(raw_chunks) and 
                   current_size + len(raw_chunks[i + 1]) <= self.chunk_size):
                i += 1
                current_chunk += " " + raw_chunks[i]
                current_size = len(current_chunk)
            
            if current_chunk.strip():
                chunk = ChunkResult(
                    content=current_chunk.strip(),
                    start_index=start_idx,
                    end_index=start_idx + len(current_chunk),
                    chunk_type="recursive_fallback",
                    metadata={'merged_chunks': 1}
                )
                chunks.append(chunk)
                start_idx += len(current_chunk) - self.chunk_overlap
            
            i += 1
        
        return chunks
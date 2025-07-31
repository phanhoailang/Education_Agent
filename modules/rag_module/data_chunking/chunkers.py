import time
import re
import logging
from typing import List, Dict, Any, Optional, Union
from pathlib import Path

from .chunking_strategies import (
    ChunkingStrategy, 
    FixedSizeStrategy, 
    SentenceAwareStrategy,
    SemanticStrategy,
    RecursiveStrategy,
    ChunkResult
)
from .preprocessor import VietnameseTextPreprocessor
from .chunk_metadata import ChunkMetadata

class BaseVietnameseChunker:
    """Base class cho Vietnamese text chunkers."""
    
    def __init__(self, 
                 preprocessor: Optional[VietnameseTextPreprocessor] = None,
                 min_chunk_size: int = 50,
                 max_chunk_size: int = 2000,
                 overlap_ratio: float = 0.1):
        """
        Args:
            preprocessor: Preprocessor cho văn bản tiếng Việt
            min_chunk_size: Kích thước chunk tối thiểu
            max_chunk_size: Kích thước chunk tối đa
            overlap_ratio: Tỷ lệ overlap giữa các chunks
        """
        self.preprocessor = preprocessor or VietnameseTextPreprocessor()
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap_ratio = overlap_ratio
        
        self.logger = logging.getLogger(__name__)
    
    def _create_chunk_metadata(self, 
                              chunk_result: ChunkResult,
                              chunk_index: int,
                              strategy_name: str) -> ChunkMetadata:
        """Tạo metadata cho chunk (simplified version)."""
        
        # Lấy thông tin ngôn ngữ tiếng Việt (bỏ NER để tăng tốc)
        vietnamese_features = {}
        pos_tags = []
        
        try:
            # POS tagging (optional, có thể bỏ nếu muốn tăng tốc hơn)
            pos_result = self.preprocessor.get_pos_tags(chunk_result.content)
            pos_tags = [tag for word, tag in pos_result]
            
            # Thống kê văn bản
            stats = self.preprocessor.get_text_statistics(chunk_result.content)
            vietnamese_features = {
                'avg_words_per_sentence': stats.avg_words_per_sentence,
                'avg_chars_per_word': stats.avg_chars_per_word,
                'vietnamese_chars_ratio': stats.vietnamese_chars_count / len(chunk_result.content) if chunk_result.content else 0,
                'paragraph_count': stats.paragraph_count
            }
            
        except Exception as e:
            self.logger.warning(f"Error extracting Vietnamese features: {e}")
        
        # Tính điểm chất lượng chunk
        coherence_score = self._calculate_coherence_score(chunk_result.content)
        completeness_score = self._calculate_completeness_score(chunk_result.content)
        
        # Trích xuất keywords đơn giản
        keywords = self._extract_keywords(chunk_result.content)
        
        metadata = ChunkMetadata(
            chunk_index=chunk_index,
            content=chunk_result.content,
            char_start=chunk_result.start_index,
            char_end=chunk_result.end_index,
            chunking_strategy=strategy_name,
            vietnamese_features=vietnamese_features,
            pos_tags=pos_tags,
            semantic_coherence_score=coherence_score,
            completeness_score=completeness_score,
            keywords=keywords,
            language_confidence=self.preprocessor.detect_language_confidence(chunk_result.content)
        )
        
        # Thêm metadata từ ChunkResult
        if chunk_result.metadata:
            for key, value in chunk_result.metadata.items():
                if hasattr(metadata, key):
                    setattr(metadata, key, value)
                else:
                    metadata.vietnamese_features[key] = value
        
        return metadata
    
    def _calculate_coherence_score(self, text: str) -> float:
        """Tính điểm coherence của chunk."""
        if not text or len(text) < 10:
            return 0.0
        
        # Kiểm tra tính hoàn thiện của câu
        sentences = self.preprocessor.tokenize_sentences(text)
        if not sentences:
            return 0.5
        
        complete_sentences = 0
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and sentence[-1] in '.!?':
                complete_sentences += 1
        
        sentence_completeness = complete_sentences / len(sentences) if sentences else 0
        
        # Kiểm tra độ dài hợp lý
        length_score = 1.0
        if len(text) < self.min_chunk_size:
            length_score = len(text) / self.min_chunk_size
        elif len(text) > self.max_chunk_size:
            length_score = self.max_chunk_size / len(text)
        
        # Kết hợp các điểm
        coherence_score = (sentence_completeness * 0.7 + length_score * 0.3)
        return min(coherence_score, 1.0)
    
    def _calculate_completeness_score(self, text: str) -> float:
        """Tính điểm completeness của chunk."""
        if not text:
            return 0.0
        
        # Kiểm tra chunk có bắt đầu và kết thúc tự nhiên không
        text = text.strip()
        
        # Điểm cho việc bắt đầu
        start_score = 1.0
        if text and text[0].islower():
            # Có thể chunk bắt đầu giữa câu
            start_score = 0.7
        
        # Điểm cho việc kết thúc
        end_score = 1.0
        if text and text[-1] not in '.!?':
            # Chunk kết thúc không hoàn thiện
            end_score = 0.6
        
        # Điểm tổng thể
        completeness_score = (start_score + end_score) / 2
        return completeness_score
    
    def _extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """Trích xuất keywords đơn giản từ text."""
        if not text:
            return []
        
        # Tokenize words
        words = self.preprocessor.tokenize_words(text.lower())
        
        # Filter stopwords (từ dừng tiếng Việt cơ bản)
        vietnamese_stopwords = {
            'và', 'của', 'có', 'là', 'trong', 'với', 'được', 'cho', 'từ', 'một',
            'các', 'này', 'đó', 'để', 'người', 'những', 'việc', 'như', 'về', 'sau',
            'trước', 'khi', 'đã', 'sẽ', 'đang', 'bị', 'theo', 'cả', 'còn', 'lại',
            'mà', 'nếu', 'thì', 'chỉ', 'cũng', 'rất', 'nhiều', 'lớn', 'nhỏ'
        }
        
        # Đếm frequency và filter
        word_freq = {}
        for word in words:
            if (len(word) > 2 and 
                word not in vietnamese_stopwords and
                not word.isdigit()):
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Sắp xếp theo frequency và trả về top keywords
        keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in keywords[:max_keywords]]

class VietnameseTextChunker(BaseVietnameseChunker):
    """Chunker cơ bản cho văn bản tiếng Việt với một strategy duy nhất."""
    
    def __init__(self, 
                 strategy: ChunkingStrategy,
                 preprocessor: Optional[VietnameseTextPreprocessor] = None,
                 **kwargs):
        """
        Args:
            strategy: Chiến lược chunking sử dụng
            preprocessor: Text preprocessor
        """
        super().__init__(preprocessor=preprocessor, **kwargs)
        self.strategy = strategy
    
    def chunk_text(self, 
                   text: str,
                   source_info: Optional[Dict[str, Any]] = None) -> List[ChunkMetadata]:
        """
        Chia văn bản thành chunks.
        
        Args:
            text: Văn bản markdown cần chia
            source_info: Thông tin về nguồn văn bản (optional, không lưu vào chunks)
            
        Returns:
            Danh sách ChunkMetadata (không chứa source info)
        """
        if not text or not text.strip():
            return []
        
        start_time = time.time()
        
        # Tiền xử lý văn bản
        processed_text = self.preprocessor.preprocess(text)
        
        # Chunking
        chunk_results = self.strategy.split_text(processed_text)
        
        # Tạo metadata cho từng chunk (không bao gồm source_info)
        chunks_metadata = []
        for i, chunk_result in enumerate(chunk_results):
            if len(chunk_result.content.strip()) >= self.min_chunk_size:
                metadata = self._create_chunk_metadata(
                    chunk_result=chunk_result,
                    chunk_index=i,
                    strategy_name=self.strategy.name
                )
                metadata.processing_time = time.time() - start_time
                chunks_metadata.append(metadata)
        
        self.logger.info(f"Created {len(chunks_metadata)} chunks using {self.strategy.name} strategy")
        return chunks_metadata

class HybridVietnameseChunker(BaseVietnameseChunker):
    """Chunker hybrid sử dụng nhiều strategies và chọn kết quả tốt nhất."""
    
    def __init__(self,
                 strategies: List[ChunkingStrategy],
                 selection_criteria: str = "best_coherence",
                 preprocessor: Optional[VietnameseTextPreprocessor] = None,
                 **kwargs):
        """
        Args:
            strategies: Danh sách các strategies
            selection_criteria: Tiêu chí chọn strategy ("best_coherence", "most_chunks", "target_size")
            preprocessor: Text preprocessor
        """
        super().__init__(preprocessor=preprocessor, **kwargs)
        self.strategies = strategies
        self.selection_criteria = selection_criteria
    
    def chunk_text(self, 
                   text: str,
                   source_info: Optional[Dict[str, Any]] = None,
                   target_chunk_count: Optional[int] = None) -> List[ChunkMetadata]:
        """
        Chia văn bản sử dụng strategy tốt nhất.
        
        Args:
            text: Văn bản cần chia
            source_info: Thông tin nguồn
            target_chunk_count: Số chunks mong muốn (dùng cho selection)
            
        Returns:
            Danh sách ChunkMetadata từ strategy tốt nhất
        """
        if not text or not text.strip():
            return []
        
        start_time = time.time()
        source_info = source_info or {}
        
        # Thử tất cả strategies
        all_results = {}
        
        for strategy in self.strategies:
            try:
                chunker = VietnameseTextChunker(strategy, self.preprocessor)
                chunks = chunker.chunk_text(text, source_info)
                all_results[strategy.name] = chunks
                
                self.logger.debug(f"Strategy {strategy.name}: {len(chunks)} chunks")
                
            except Exception as e:
                self.logger.error(f"Strategy {strategy.name} failed: {e}")
                continue
        
        if not all_results:
            self.logger.error("All chunking strategies failed")
            return []
        
        # Chọn strategy tốt nhất
        best_strategy_name = self._select_best_strategy(
            all_results, 
            target_chunk_count
        )
        
        best_chunks = all_results[best_strategy_name]
        
        # Cập nhật processing time
        processing_time = time.time() - start_time
        for chunk in best_chunks:
            chunk.processing_time = processing_time
            chunk.chunking_strategy = f"hybrid_{best_strategy_name}"
        
        self.logger.info(
            f"Selected {best_strategy_name} strategy with {len(best_chunks)} chunks "
            f"(criteria: {self.selection_criteria})"
        )
        
        return best_chunks
    
    def _select_best_strategy(self, 
                             all_results: Dict[str, List[ChunkMetadata]],
                             target_chunk_count: Optional[int] = None) -> str:
        """Chọn strategy tốt nhất dựa trên tiêu chí."""
        
        if len(all_results) == 1:
            return list(all_results.keys())[0]
        
        strategy_scores = {}
        
        for strategy_name, chunks in all_results.items():
            score = 0.0
            
            if self.selection_criteria == "best_coherence":
                # Tính điểm coherence trung bình
                coherence_scores = [
                    chunk.semantic_coherence_score or 0.0 
                    for chunk in chunks
                ]
                score = sum(coherence_scores) / len(coherence_scores) if coherence_scores else 0.0
                
            elif self.selection_criteria == "most_chunks":
                # Ưu tiên strategy tạo nhiều chunks nhất
                score = len(chunks)
                
            elif self.selection_criteria == "target_size":
                # Ưu tiên strategy có chunk size gần target nhất
                if target_chunk_count:
                    score = 1.0 / (abs(len(chunks) - target_chunk_count) + 1)
                else:
                    # Mặc định target size ~ 1000 chars
                    target_size = 1000
                    size_diffs = [
                        abs(len(chunk.content) - target_size) 
                        for chunk in chunks
                    ]
                    avg_diff = sum(size_diffs) / len(size_diffs) if size_diffs else 1000
                    score = 1.0 / (avg_diff + 1)
            
            elif self.selection_criteria == "balanced":
                # Kết hợp nhiều tiêu chí
                coherence_scores = [
                    chunk.semantic_coherence_score or 0.0 
                    for chunk in chunks
                ]
                avg_coherence = sum(coherence_scores) / len(coherence_scores) if coherence_scores else 0.0
                
                completeness_scores = [
                    chunk.completeness_score or 0.0 
                    for chunk in chunks
                ]
                avg_completeness = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0.0
                
                # Điểm cho số lượng chunks hợp lý (không quá ít, không quá nhiều)
                chunk_count_score = min(len(chunks) / 10.0, 1.0)  # Tối đa 10 chunks = 1.0 điểm
                
                score = (avg_coherence * 0.4 + 
                        avg_completeness * 0.4 + 
                        chunk_count_score * 0.2)
            
            strategy_scores[strategy_name] = score
        
        # Trả về strategy có điểm cao nhất
        best_strategy = max(strategy_scores, key=strategy_scores.get)
        
        self.logger.debug(f"Strategy scores: {strategy_scores}")
        return best_strategy

class SemanticVietnameseChunker(BaseVietnameseChunker):
    """Chunker chuyên biệt cho semantic chunking với tiếng Việt."""
    
    def __init__(self,
                 embedding_model: str = "dangvantuan/vietnamese-embedding",
                 similarity_threshold: float = 0.75,
                 min_similarity_window: int = 3,
                 adaptive_threshold: bool = True,
                 preprocessor: Optional[VietnameseTextPreprocessor] = None,
                 **kwargs):
        """
        Args:
            embedding_model: Model embedding cho tiếng Việt
            similarity_threshold: Ngưỡng similarity để tách chunks
            min_similarity_window: Số câu tối thiểu để tính similarity
            adaptive_threshold: Tự động điều chỉnh threshold
            preprocessor: Text preprocessor
        """
        super().__init__(preprocessor=preprocessor, **kwargs)
        self.embedding_model = embedding_model
        self.similarity_threshold = similarity_threshold
        self.min_similarity_window = min_similarity_window
        self.adaptive_threshold = adaptive_threshold
        
        # Fallback strategies nếu semantic chunking thất bại
        self.fallback_strategies = [
            SentenceAwareStrategy(target_size=1000),
            RecursiveStrategy(chunk_size=1000, chunk_overlap=200)
        ]
    
    def chunk_text(self, 
                   text: str,
                   source_info: Optional[Dict[str, Any]] = None) -> List[ChunkMetadata]:
        """
        Chia văn bản bằng semantic chunking.
        
        Args:
            text: Văn bản cần chia
            source_info: Thông tin nguồn
            
        Returns:
            Danh sách ChunkMetadata
        """
        if not text or not text.strip():
            return []
        
        start_time = time.time()
        source_info = source_info or {}
        
        # Thử semantic chunking trước
        try:
            # Điều chỉnh threshold nếu cần
            if self.adaptive_threshold:
                adaptive_threshold = self._calculate_adaptive_threshold(text)
            else:
                adaptive_threshold = self.similarity_threshold
            
            semantic_strategy = SemanticStrategy(
                model_name=self.embedding_model,
                similarity_threshold=adaptive_threshold,
                target_size=1000
            )
            
            chunker = VietnameseTextChunker(semantic_strategy, self.preprocessor)
            chunks = chunker.chunk_text(text, source_info)
            
            # Kiểm tra chất lượng kết quả
            if self._validate_semantic_chunks(chunks):
                processing_time = time.time() - start_time
                for chunk in chunks:
                    chunk.processing_time = processing_time
                    chunk.chunking_strategy = f"semantic_vietnamese"
                
                self.logger.info(f"Semantic chunking successful: {len(chunks)} chunks")
                return chunks
            else:
                self.logger.warning("Semantic chunking quality validation failed, using fallback")
                
        except Exception as e:
            self.logger.error(f"Semantic chunking failed: {e}")
        
        # Fallback: Thử các strategies khác
        for strategy in self.fallback_strategies:
            try:
                chunker = VietnameseTextChunker(strategy, self.preprocessor)
                chunks = chunker.chunk_text(text, source_info)
                
                if chunks:
                    processing_time = time.time() - start_time
                    for chunk in chunks:
                        chunk.processing_time = processing_time
                        chunk.chunking_strategy = f"semantic_fallback_{strategy.name}"
                    
                    self.logger.info(f"Fallback strategy {strategy.name} used: {len(chunks)} chunks")
                    return chunks
                    
            except Exception as e:
                self.logger.error(f"Fallback strategy {strategy.name} failed: {e}")
                continue
        
        self.logger.error("All chunking strategies failed")
        return []
    
    def _calculate_adaptive_threshold(self, text: str) -> float:
        """Tính threshold adaptive dựa trên đặc điểm văn bản."""
        stats = self.preprocessor.get_text_statistics(text)
        
        # Văn bản có câu ngắn -> threshold thấp hơn
        if stats.avg_words_per_sentence < 10:
            return self.similarity_threshold - 0.1
        
        # Văn bản có câu dài -> threshold cao hơn
        elif stats.avg_words_per_sentence > 20:
            return self.similarity_threshold + 0.05
        
        # Văn bản có nhiều đoạn -> threshold cao hơn
        if stats.paragraph_count > 10:
            return self.similarity_threshold + 0.05
        
        return self.similarity_threshold
    
    def _validate_semantic_chunks(self, chunks: List[ChunkMetadata]) -> bool:
        """Kiểm tra chất lượng semantic chunks."""
        if not chunks:
            return False
        
        # Kiểm tra có quá ít chunks không
        if len(chunks) < 2:
            return False
        
        # Kiểm tra chunks có quá ngắn không
        short_chunks = [c for c in chunks if len(c.content) < self.min_chunk_size]
        if len(short_chunks) > len(chunks) * 0.3:  # Quá 30% chunks ngắn
            return False
        
        # Kiểm tra coherence score trung bình
        coherence_scores = [
            chunk.semantic_coherence_score or 0.0 
            for chunk in chunks
        ]
        avg_coherence = sum(coherence_scores) / len(coherence_scores)
        
        if avg_coherence < 0.6:  # Coherence quá thấp
            return False
        
        return True

class RecursiveVietnameseChunker(BaseVietnameseChunker):
    """Chunker tối ưu cho tiếng Việt sử dụng recursive splitting."""
    
    def __init__(self,
                 base_chunk_size: int = 1000,
                 overlap_ratio: float = 0.2,
                 adaptive_sizing: bool = True,
                 preserve_sentences: bool = True,
                 preprocessor: Optional[VietnameseTextPreprocessor] = None,
                 **kwargs):
        """
        Args:
            base_chunk_size: Kích thước chunk cơ bản
            overlap_ratio: Tỷ lệ overlap
            adaptive_sizing: Tự động điều chỉnh kích thước chunk
            preserve_sentences: Bảo toàn ranh giới câu
            preprocessor: Text preprocessor
        """
        super().__init__(preprocessor=preprocessor, **kwargs)
        self.base_chunk_size = base_chunk_size
        self.overlap_ratio = overlap_ratio
        self.adaptive_sizing = adaptive_sizing
        self.preserve_sentences = preserve_sentences
    
    def chunk_text(self, 
                   text: str,
                   source_info: Optional[Dict[str, Any]] = None) -> List[ChunkMetadata]:
        """
        Chia văn bản bằng recursive chunking tối ưu cho tiếng Việt.
        
        Args:
            text: Văn bản cần chia
            source_info: Thông tin nguồn
            
        Returns:
            Danh sách ChunkMetadata
        """
        if not text or not text.strip():
            return []
        
        start_time = time.time()
        source_info = source_info or {}
        
        # Tính toán kích thước chunk tối ưu
        if self.adaptive_sizing:
            chunk_size = self._calculate_optimal_chunk_size(text)
        else:
            chunk_size = self.base_chunk_size
        
        overlap_size = int(chunk_size * self.overlap_ratio)
        
        # Tạo separators tối ưu cho tiếng Việt
        vietnamese_separators = self._get_vietnamese_separators()
        
        strategy = RecursiveStrategy(
            chunk_size=chunk_size,
            chunk_overlap=overlap_size,
            vietnamese_separators=True
        )
        strategy.separators = vietnamese_separators
        
        # Chunking
        chunker = VietnameseTextChunker(strategy, self.preprocessor)
        chunks = chunker.chunk_text(text, source_info)
        
        # Post-processing: Cải thiện chất lượng chunks
        if self.preserve_sentences:
            chunks = self._post_process_sentence_boundaries(chunks, text)
        
        # Cập nhật metadata
        processing_time = time.time() - start_time
        for chunk in chunks:
            chunk.processing_time = processing_time
            chunk.chunking_strategy = "recursive_vietnamese_optimized"
            chunk.vietnamese_features['adaptive_chunk_size'] = chunk_size
            chunk.vietnamese_features['overlap_ratio'] = self.overlap_ratio
        
        self.logger.info(f"Recursive Vietnamese chunking: {len(chunks)} chunks (size: {chunk_size})")
        return chunks
    
    def _calculate_optimal_chunk_size(self, text: str) -> int:
        """Tính toán kích thước chunk tối ưu dựa trên văn bản."""
        stats = self.preprocessor.get_text_statistics(text)
        
        # Dựa trên độ dài trung bình của câu
        if stats.avg_words_per_sentence < 8:
            # Câu ngắn -> chunk nhỏ hơn
            optimal_size = int(self.base_chunk_size * 0.8)
        elif stats.avg_words_per_sentence > 25:
            # Câu dài -> chunk lớn hơn
            optimal_size = int(self.base_chunk_size * 1.3)
        else:
            optimal_size = self.base_chunk_size
        
        # Điều chỉnh theo số đoạn văn
        if stats.paragraph_count > 20:
            # Nhiều đoạn -> chunk nhỏ hơn để bảo toàn cấu trúc
            optimal_size = int(optimal_size * 0.9)
        
        # Giới hạn trong khoảng hợp lý
        optimal_size = max(self.min_chunk_size * 2, optimal_size)
        optimal_size = min(self.max_chunk_size, optimal_size)
        
        return optimal_size
    
    def _get_vietnamese_separators(self) -> List[str]:
        """Tạo danh sách separators tối ưu cho tiếng Việt."""
        return [
            "\n\n\n",  # Multiple paragraph breaks
            "\n\n",    # Paragraph breaks
            "\n",      # Line breaks
            ". ",      # Sentence endings
            "! ",      # Exclamation
            "? ",      # Question
            "; ",      # Semicolon
            ", ",      # Comma
            " - ",     # Dash with spaces
            " ",       # Word breaks
            ""         # Character level
        ]
    
    def _post_process_sentence_boundaries(self, 
                                        chunks: List[ChunkMetadata],
                                        original_text: str) -> List[ChunkMetadata]:
        """Cải thiện ranh giới câu trong chunks."""
        if not chunks:
            return chunks
        
        improved_chunks = []
        
        for i, chunk in enumerate(chunks):
            content = chunk.content.strip()
            
            # Kiểm tra chunk có kết thúc giữa câu không
            if not content.endswith(('.', '!', '?', '\n')):
                # Thử mở rộng đến cuối câu
                next_chunk_start = chunks[i + 1].char_start if i + 1 < len(chunks) else len(original_text)
                
                # Tìm kết thúc câu trong khoảng hợp lý
                search_end = min(chunk.char_end + 200, next_chunk_start)
                search_text = original_text[chunk.char_end:search_end]
                
                sentence_end_match = re.search(r'[.!?]\s', search_text)
                if sentence_end_match:
                    extend_chars = sentence_end_match.end()
                    new_content = content + search_text[:extend_chars].rstrip()
                    
                    # Cập nhật chunk
                    chunk.content = new_content
                    chunk.char_end = chunk.char_end + extend_chars
                    chunk.char_count = len(new_content)
                    chunk.word_count = len(new_content.split())
                    
                    # Recalculate scores
                    chunk.semantic_coherence_score = self._calculate_coherence_score(new_content)
                    chunk.completeness_score = self._calculate_completeness_score(new_content)
            
            improved_chunks.append(chunk)
        
        return improved_chunks
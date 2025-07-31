import json
import logging
import re
from typing import List, Set, Dict
from functools import lru_cache
from modules.rag_module.datatypes.CoverageAssessment import CoverageAssessment
from modules.rag_module.datatypes.CoverageLevel import CoverageLevel

class CoverageEvaluatorAgent:
    def __init__(self, llm, max_content_length: int = 4000):
        self.llm = llm
        self.max_content_length = max_content_length
        self.logger = logging.getLogger(__name__)
        
        # Fast heuristic weights
        self.keyword_weight = 0.4
        self.length_weight = 0.3
        self.source_diversity_weight = 0.2
        self.quality_weight = 0.1
        
        # Thresholds for fast decisions
        self.high_confidence_threshold = 0.8
        self.low_confidence_threshold = 0.3
        
        # Performance counters
        self.fast_decisions = 0
        self.llm_calls = 0
        
        self.prompt = """
        Bạn là một chuyên gia giáo dục, có nhiệm vụ **đánh giá nội dung bài giảng** với thái độ khuyến khích, linh hoạt và mang tính xây dựng.

        ## MỤC TIÊU
        Đánh giá mức độ đầy đủ và chất lượng của nội dung hiện có, nhằm xác định xem nội dung đó đã đủ cơ sở để phát triển thành một bài giảng hoàn chỉnh chưa.

        ## THÔNG TIN ĐẦU VÀO:
        **Yêu cầu bài giảng**: {request}
        **Các chủ đề quan trọng**: {required_topics}
        **Nội dung hiện tại**: {content}

        ## KHUNG ĐÁNH GIÁ LINH HOẠT:
        1. Độ bao phủ chủ đề (25%): Kiểm tra các chủ đề chính, chấp nhận cách tiếp cận đa dạng
        2. Chất lượng nội dung (35%): Tính chính xác cơ bản, độ rõ ràng, có thể bổ sung sau
        3. Tính khả thi bài giảng (25%): Đủ ý tưởng chính để phát triển, có tiềm năng mở rộng
        4. Giá trị giáo dục (15%): Có ích cho học viên, phù hợp với mục tiêu học tập

        ## THANG ĐIỂM KHUYẾN KHÍCH:
        - INSUFFICIENT (0.0-0.4): Nội dung đang phát triển, có nền tảng tốt để xây dựng thêm
        - PARTIAL (0.4-0.7): Nội dung tốt, bao phủ được phần lớn yêu cầu, có thể hoàn thiện
        - ADEQUATE (0.7-0.9): Nội dung xuất sắc, đầy đủ chi tiết, sẵn sàng tạo bài giảng
        - COMPREHENSIVE (0.9-1.0): Nội dung vượt trội, phong phú, có nhiều góc nhìn thú vị

        ## LƯU Ý ĐÁNH GIÁ:
        - Tập trung vào điểm mạnh và tiềm năng của nội dung
        - Chấp nhận những cách tiếp cận khác nhau miễn là hợp lý
        - Khuyến khích sự sáng tạo và góc nhìn mới
        - Ưu tiên tính thực tiễn hơn là hoàn hảo về mặt lý thuyết

        Trả về JSON:
        ```json
        {{
            "level": "developing|good|excellent|outstanding",
            "score": 0.0,
            "covered_topics": ["topic1", "topic2"],
            "missing_topics": ["topic3"],
            "strengths": ["điểm mạnh 1", "điểm mạnh 2"],
            "suggestions": ["gợi ý cải thiện 1", "gợi ý cải thiện 2"]
        }}
        ```

        CHỈ trả về JSON hợp lệ, không thêm văn bản khác.
    """

    @lru_cache(maxsize=100)
    def extract_keywords(self, text: str) -> frozenset:
        """Extract và cache keywords từ text"""
        # Remove diacritics for better matching
        import unicodedata
        text_normalized = unicodedata.normalize('NFD', text.lower())
        text_ascii = ''.join(char for char in text_normalized if unicodedata.category(char) != 'Mn')
        
        # Extract meaningful words (length >= 3, không phải stop words)
        words = re.findall(r'\b\w{3,}\b', text_ascii)
        
        # Vietnamese stop words (basic set)
        stop_words = {
            'the', 'and', 'hoac', 'cua', 'voi', 'trong', 'ngoai', 'tren', 'duoi',
            'khi', 'neu', 'thi', 'cho', 'den', 'tai', 'ban', 'cac', 'mot', 'hai',
            'la', 'co', 'khong', 'duoc', 'tim', 'hoc', 'sinh', 'giao', 'vien'
        }
        
        keywords = {word for word in words if word not in stop_words and len(word) >= 3}
        return frozenset(keywords)

    def quick_coverage_assessment(self, request: str, subtopics: List[str], chunks: List) -> tuple:
        """🚀 Fast heuristic assessment trước khi gọi LLM"""
        
        if not chunks:
            return False, 0.0, "no_chunks"
        
        # 1. Extract keywords from request and subtopics
        request_keywords = self.extract_keywords(request)
        topic_keywords = set()
        for topic in subtopics:
            topic_keywords.update(self.extract_keywords(topic))
        
        required_keywords = request_keywords | topic_keywords
        
        # 2. Extract keywords from chunks
        covered_keywords = set()
        total_content_length = 0
        sources = set()
        high_score_chunks = 0
        
        for chunk in chunks:
            content = chunk.content if hasattr(chunk, 'content') else chunk.get('content', '')
            score = chunk.score if hasattr(chunk, 'score') else chunk.get('score', 0)
            source = chunk.source_file if hasattr(chunk, 'source_file') else chunk.get('source_file', '')
            
            if content:
                covered_keywords.update(self.extract_keywords(content))
                total_content_length += len(content)
                
            if source:
                sources.add(source)
                
            if score > 0.7:  # High relevance chunks
                high_score_chunks += 1
        
        # 3. Calculate coverage metrics
        keyword_coverage = len(covered_keywords & required_keywords) / max(len(required_keywords), 1)
        length_score = min(total_content_length / 5000, 1.0)  # 5k chars = good coverage
        source_diversity = min(len(sources) / 3, 1.0)  # 3+ sources = good diversity  
        quality_score = min(high_score_chunks / max(len(chunks), 1), 1.0)
        
        # 4. Weighted composite score
        composite_score = (
            keyword_coverage * self.keyword_weight +
            length_score * self.length_weight +
            source_diversity * self.source_diversity_weight +
            quality_score * self.quality_weight
        )
        
        # 5. Fast decision thresholds
        if composite_score >= self.high_confidence_threshold:
            decision = True
            reason = "high_confidence_heuristic"
        elif composite_score <= self.low_confidence_threshold:
            decision = False
            reason = "low_confidence_heuristic"
        else:
            decision = None  # Uncertain, need LLM
            reason = "uncertain_need_llm"
        
        self.logger.debug(f"Quick assessment: keyword={keyword_coverage:.2f}, "
                         f"length={length_score:.2f}, sources={source_diversity:.2f}, "
                         f"quality={quality_score:.2f}, composite={composite_score:.2f}")
        
        return decision, composite_score, reason

    def optimize_content_fast(self, chunks: List, target_length: int = None) -> str:
        """🚀 Optimized content preparation với early termination"""
        if not chunks:
            return ""
        
        target_length = target_length or self.max_content_length
        
        # Sort by score (không thay đổi original list)
        sorted_chunks = sorted(chunks, key=lambda x: getattr(x, 'score', 0) 
                              if hasattr(x, 'score') else x.get('score', 0), reverse=True)
        
        content_parts = []
        total_length = 0
        sources_seen = set()
        
        for chunk in sorted_chunks:
            content = chunk.content if hasattr(chunk, 'content') else chunk.get('content', '')
            source = chunk.source_file if hasattr(chunk, 'source_file') else chunk.get('source_file', 'Unknown')
            
            if not content:
                continue
                
            # Diversify sources - prefer chunks from different sources
            source_bonus = 0 if source in sources_seen else 200
            
            text_snippet = f"[Nguồn: {source}] {content}"
            
            # Check if adding this chunk would exceed limit
            if total_length + len(text_snippet) + source_bonus <= target_length:
                content_parts.append(text_snippet)
                total_length += len(text_snippet)
                sources_seen.add(source)
            else:
                # Try to fit a truncated version
                remaining_space = target_length - total_length - 50  # Buffer
                if remaining_space > 200:  # Worth truncating
                    truncated = content[:remaining_space] + "..."
                    text_snippet = f"[Nguồn: {source}] {truncated}"
                    content_parts.append(text_snippet)
                break
        
        return "\n\n".join(content_parts)

    def run(self, request: str, subtopics: List[str], chunks: List) -> CoverageAssessment:
        """🚀 OPTIMIZED coverage evaluation với fast path"""
        try:
            # Step 1: Quick heuristic assessment
            quick_decision, heuristic_score, reason = self.quick_coverage_assessment(
                request, subtopics, chunks
            )
            
            if quick_decision is not None:
                # Fast path: confident heuristic decision
                self.fast_decisions += 1
                
                if quick_decision:
                    level = self._score_to_level(heuristic_score)
                    self.logger.info(f"✅ Fast decision: {level.value} (score={heuristic_score:.2f}, reason={reason})")
                    
                    return CoverageAssessment(
                        level=level,
                        score=heuristic_score,
                        missing_topics=[],  # Assume covered in fast positive case
                        covered_topics=subtopics,
                    )
                else:
                    self.logger.info(f"❌ Fast decision: INSUFFICIENT (score={heuristic_score:.2f}, reason={reason})")
                    
                    return CoverageAssessment(
                        level=CoverageLevel.INSUFFICIENT,
                        score=heuristic_score,
                        missing_topics=subtopics,
                        covered_topics=[],
                    )
            
            # Step 2: Uncertain case - use LLM
            self.llm_calls += 1
            self.logger.info(f"🤔 Uncertain case, using LLM (heuristic_score={heuristic_score:.2f})")
            
            content = self.optimize_content_fast(chunks)
            
            if not content.strip():
                self.logger.warning("No valid content for LLM assessment")
                return CoverageAssessment(
                    level=CoverageLevel.INSUFFICIENT,
                    score=0.0,
                    missing_topics=subtopics,
                    covered_topics=[],
                )
            
            prompt = self.prompt.format(
                request=request,
                required_topics=", ".join(subtopics),
                content=content
            )
            
            messages = [{"role": "user", "content": prompt}]
            result = self.llm.chat(messages, temperature=0.2, max_tokens=1500)

            # Parse LLM response
            parsed_result = self._parse_llm_response(result, subtopics, heuristic_score)
            
            self.logger.info(f"🧠 LLM decision: {parsed_result.level.value} (score={parsed_result.score:.2f})")
            return parsed_result
            
        except Exception as e:
            self.logger.error(f"Coverage evaluation error: {e}")
            return self._fallback_assessment(subtopics)

    def _parse_llm_response(self, result: str, subtopics: List[str], 
                           heuristic_score: float) -> CoverageAssessment:
        """Parse LLM response với fallbacks"""
        try:
            # Clean JSON from markdown
            if result.startswith("```json"):
                result = result.lstrip("```json").rstrip("```\n").strip()
            elif result.startswith("```"):
                result = result.lstrip("```").rstrip("```\n").strip()

            parsed = json.loads(result)
            
            # Validate and clean level
            level_str = parsed.get("level", "insufficient").lower()
            if level_str not in [e.value for e in CoverageLevel]:
                level_str = "insufficient"
            
            # Use heuristic score as baseline, adjust with LLM confidence
            llm_score = float(parsed.get("score", heuristic_score))
            
            # Blend heuristic and LLM scores (70% LLM, 30% heuristic)
            final_score = 0.7 * llm_score + 0.3 * heuristic_score
            
            return CoverageAssessment(
                level=CoverageLevel(level_str),
                score=final_score,
                missing_topics=self._clean_topic_list(parsed.get("missing_topics", [])),
                covered_topics=self._clean_topic_list(parsed.get("covered_topics", []))
            )
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"JSON parse error: {e}")
            return self._fallback_assessment(subtopics, heuristic_score)
        except Exception as e:
            self.logger.error(f"Error parsing LLM response: {e}")
            return self._fallback_assessment(subtopics, heuristic_score)

    def _clean_topic_list(self, topics: List) -> List[str]:
        """Clean và validate topic list"""
        if not isinstance(topics, list):
            return []
        
        cleaned = []
        for topic in topics:
            if isinstance(topic, str):
                clean_topic = topic.strip().strip('",•').replace('",', '')
                if clean_topic:
                    cleaned.append(clean_topic)
        
        return cleaned

    def _score_to_level(self, score: float) -> CoverageLevel:
        """Convert numeric score to CoverageLevel"""
        if score >= 0.9:
            return CoverageLevel.OUTSTANDING
        elif score >= 0.7:
            return CoverageLevel.EXCELLENT  
        elif score >= 0.4:
            return CoverageLevel.GOOD
        elif score >= 0.0:
            return CoverageLevel.DEVELOPING
        else:
            return CoverageLevel.INSUFFICIENT

    def _fallback_assessment(self, subtopics: List[str], 
                           score: float = 0.0) -> CoverageAssessment:
        """Fallback assessment when LLM fails"""
        return CoverageAssessment(
            level=CoverageLevel.INSUFFICIENT,
            score=score,
            missing_topics=subtopics,
            covered_topics=[],
        )

    def get_performance_stats(self) -> Dict[str, any]:
        """Get performance statistics"""
        total_calls = self.fast_decisions + self.llm_calls
        fast_decision_rate = self.fast_decisions / total_calls if total_calls > 0 else 0
        
        return {
            "total_evaluations": total_calls,
            "fast_decisions": self.fast_decisions,
            "llm_calls": self.llm_calls,
            "fast_decision_rate": fast_decision_rate,
            "avg_speedup": f"{(1 - fast_decision_rate) * 100:.1f}% calls avoided LLM"
        }

    def reset_stats(self):
        """Reset performance counters"""
        self.fast_decisions = 0
        self.llm_calls = 0

    def configure_thresholds(self, high_confidence: float = None, 
                           low_confidence: float = None):
        """Configure decision thresholds for tuning"""
        if high_confidence is not None:
            self.high_confidence_threshold = high_confidence
        if low_confidence is not None:
            self.low_confidence_threshold = low_confidence
            
        self.logger.info(f"Thresholds updated: high={self.high_confidence_threshold}, "
                        f"low={self.low_confidence_threshold}")
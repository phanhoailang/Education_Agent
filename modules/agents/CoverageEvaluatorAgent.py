import json
import logging
import re
from functools import lru_cache
from typing import List, Set, Dict, Any

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

        # Prompt đồng bộ với hệ INSUFFICIENT/PARTIAL/ADEQUATE/COMPREHENSIVE
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

        ## THANG ĐIỂM
        - INSUFFICIENT (0.0–0.4)
        - PARTIAL (0.4–0.7)
        - ADEQUATE (0.7–0.9)
        - COMPREHENSIVE (0.9–1.0)

        Trả về JSON:
        ```json
        {{
            "level": "insufficient|partial|adequate|comprehensive",
            "score": 0.0,
            "covered_topics": ["topic1", "topic2"],
            "missing_topics": ["topic3"],
            "strengths": ["điểm mạnh 1", "điểm mạnh 2"],
            "suggestions": ["gợi ý cải thiện 1", "gợi ý cải thiện 2"]
        }}
        ```

        CHỈ trả về JSON hợp lệ, không thêm văn bản khác.
    """

        # (tuỳ chọn) in debug enum hiện có
        try:
            dbg = [f"{e.name} -> {getattr(e,'value','')}" for e in CoverageLevel]
            self.logger.debug("CoverageLevel members: " + " | ".join(dbg))
        except Exception:
            pass

    @lru_cache(maxsize=100)
    def extract_keywords(self, text: str) -> frozenset:
        """Extract và cache keywords từ text (bỏ dấu, bỏ stopwords đơn giản)."""
        import unicodedata
        if not text:
            return frozenset()

        text_norm = unicodedata.normalize('NFD', text.lower())
        text_ascii = ''.join(ch for ch in text_norm if unicodedata.category(ch) != 'Mn')

        words = re.findall(r'\b\w{3,}\b', text_ascii)

        stop_words = {
            'the', 'and', 'hoac', 'cua', 'voi', 'trong', 'ngoai', 'tren', 'duoi',
            'khi', 'neu', 'thi', 'cho', 'den', 'tai', 'ban', 'cac', 'mot', 'hai',
            'la', 'co', 'khong', 'duoc', 'tim', 'hoc', 'sinh', 'giao', 'vien'
        }
        keywords = {w for w in words if w not in stop_words and len(w) >= 3}
        return frozenset(keywords)

    def quick_coverage_assessment(self, request: str, subtopics: List[str], chunks: List) -> tuple:
        """🚀 Fast heuristic assessment trước khi gọi LLM."""
        if not chunks:
            return False, 0.0, "no_chunks"

        # 1) Keywords yêu cầu
        request_keywords = self.extract_keywords(request or "")
        topic_keywords: Set[str] = set()
        for t in (subtopics or []):
            topic_keywords.update(self.extract_keywords(t or ""))
        required_keywords = request_keywords | topic_keywords

        # 2) Từ khoá bao phủ + thống kê
        covered_keywords: Set[str] = set()
        total_content_length = 0
        sources = set()
        high_score_chunks = 0

        for ch in chunks:
            content = getattr(ch, 'content', None)
            if content is None:
                content = ch.get('content', '')
            score = getattr(ch, 'score', None)
            if score is None:
                score = ch.get('score', 0)
            source = getattr(ch, 'source_file', None)
            if source is None:
                source = ch.get('source_file', '')

            if content:
                covered_keywords.update(self.extract_keywords(content))
                total_content_length += len(content)

            if source:
                sources.add(source)
            if (score or 0) > 0.7:
                high_score_chunks += 1

        # 3) Tính điểm
        keyword_coverage = len(covered_keywords & required_keywords) / max(len(required_keywords), 1)
        length_score = min(total_content_length / 5000, 1.0)         # 5k chars = good
        source_diversity = min(len(sources) / 3, 1.0)                # 3+ nguồn = tốt
        quality_score = min(high_score_chunks / max(len(chunks), 1), 1.0)

        composite_score = (
            keyword_coverage * self.keyword_weight +
            length_score * self.length_weight +
            source_diversity * self.source_diversity_weight +
            quality_score * self.quality_weight
        )

        # 4) Quyết định nhanh
        if composite_score >= self.high_confidence_threshold:
            decision, reason = True, "high_confidence_heuristic"
        elif composite_score <= self.low_confidence_threshold:
            decision, reason = False, "low_confidence_heuristic"
        else:
            decision, reason = None, "uncertain_need_llm"

        self.logger.debug(
            "DBG fast: req_kw=%d, cov_kw=%d, kw_cov=%.3f, len=%d, src=%d, hi=%.3f, comp=%.3f",
            len(required_keywords), len(covered_keywords), keyword_coverage,
            total_content_length, len(sources), quality_score, composite_score
        )
        return decision, composite_score, reason

    def optimize_content_fast(self, chunks: List, target_length: int = None) -> str:
        """🚀 Chuẩn bị content tối ưu, ưu tiên đa dạng nguồn (early stop)."""
        if not chunks:
            return ""

        target_length = target_length or self.max_content_length
        sorted_chunks = sorted(
            chunks,
            key=lambda x: getattr(x, 'score', 0) if hasattr(x, 'score') else x.get('score', 0),
            reverse=True
        )

        content_parts: List[str] = []
        total_length = 0
        sources_seen = set()

        for ch in sorted_chunks:
            content = getattr(ch, 'content', None)
            if content is None:
                content = ch.get('content', '')
            source = getattr(ch, 'source_file', None)
            if source is None:
                source = ch.get('source_file', 'Unknown')

            if not content:
                continue

            is_new_source = source not in sources_seen
            source_bonus = 200 if is_new_source else 0  # ưu tiên nguồn mới

            text_snippet = f"[Nguồn: {source}] {content}"
            effective_len = max(0, len(text_snippet) - source_bonus)

            if total_length + effective_len <= target_length:
                content_parts.append(text_snippet)
                total_length += effective_len
                sources_seen.add(source)
            else:
                remaining = target_length - total_length - 50  # buffer
                if remaining > 200:
                    truncated = content[:remaining] + "..."
                    content_parts.append(f"[Nguồn: {source}] {truncated}")
                break

        return "\n\n".join(content_parts)

    def run(self, request: str, subtopics: List[str], chunks: List) -> CoverageAssessment:
        """🚀 OPTIMIZED coverage evaluation với fast path."""
        heuristic_score = 0.0  # luôn giữ để fallback có điểm nền
        try:
            quick_decision, heuristic_score, reason = self.quick_coverage_assessment(request, subtopics, chunks)

            if quick_decision is not None:
                self.fast_decisions += 1
                if quick_decision:
                    level = self._score_to_level(heuristic_score)
                    self.logger.info(
                        f"✅ Fast decision: {getattr(level,'name',level)}/{getattr(level,'value','')} "
                        f"(score={heuristic_score:.2f}, reason={reason})"
                    )
                    return CoverageAssessment(
                        level=level,
                        score=heuristic_score,
                        missing_topics=[],
                        covered_topics=subtopics,
                    )
                else:
                    level = CoverageLevel.INSUFFICIENT
                    self.logger.info(
                        f"❌ Fast decision: {level.name}/{level.value} "
                        f"(score={heuristic_score:.2f}, reason={reason})"
                    )
                    return CoverageAssessment(
                        level=level,
                        score=heuristic_score,
                        missing_topics=subtopics,
                        covered_topics=[],
                    )

            # Uncertain → gọi LLM
            self.llm_calls += 1
            self.logger.info(f"🤔 Uncertain case, using LLM (heuristic_score={heuristic_score:.2f})")

            content = self.optimize_content_fast(chunks)
            if not content.strip():
                self.logger.warning("No valid content for LLM assessment")
                return CoverageAssessment(
                    level=CoverageLevel.INSUFFICIENT,
                    score=heuristic_score,
                    missing_topics=subtopics,
                    covered_topics=[],
                )

            prompt = self.prompt.format(
                request=request,
                required_topics=", ".join(subtopics or []),
                content=content
            )
            messages = [{"role": "user", "content": prompt}]
            result = self.llm.chat(messages, temperature=0.2, max_tokens=1500)

            parsed_result = self._parse_llm_response(result, subtopics, heuristic_score)
            self.logger.info(
                f"🧠 LLM decision: {getattr(parsed_result.level,'name',parsed_result.level)}/"
                f"{getattr(parsed_result.level,'value','')} (score={parsed_result.score:.2f})"
            )
            return parsed_result

        except Exception as e:
            self.logger.error(f"Coverage evaluation error: {e}")
            return self._fallback_assessment(subtopics, heuristic_score)

    # -----------------------------
    # Helpers / parsing / mapping
    # -----------------------------
    def _parse_llm_response(self, result: Any, subtopics: List[str], heuristic_score: float) -> CoverageAssessment:
        """Parse LLM response an toàn, map level về Enum hợp lệ, blend điểm."""
        try:
            # 1) Chuẩn hoá result → string JSON
            if isinstance(result, dict):
                if "choices" in result:  # OpenAI-style
                    result = result["choices"][0]["message"]["content"]
                elif "content" in result:
                    result = result["content"]
                else:
                    result = json.dumps(result)
            elif isinstance(result, list):
                result = json.dumps(result)
            elif not isinstance(result, str):
                result = str(result)

            # 2) Ưu tiên lấy nội dung trong fenced code ```json ... ```
            m = re.search(r"```json\s*(\{.*?\})\s*```", result, flags=re.S | re.I)
            if m:
                result = m.group(1)
            else:
                # fallback: lấy object đầu tiên
                m2 = re.search(r"\{.*?\}", result, flags=re.S)
                if m2:
                    result = m2.group(0)

            parsed = json.loads(result)

            # 3) Map level → Enum (chấp nhận hệ khác)
            level_str = str(parsed.get("level", "")).strip()
            level = self._to_enum_level(level_str)

            # 4) Blend điểm
            llm_score_raw = parsed.get("score", None)
            try:
                llm_score = float(llm_score_raw) if llm_score_raw is not None else heuristic_score
            except Exception:
                llm_score = heuristic_score

            final_score = 0.7 * llm_score + 0.3 * heuristic_score

            return CoverageAssessment(
                level=level,
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
        """Làm sạch danh sách topics."""
        if not isinstance(topics, list):
            return []
        cleaned: List[str] = []
        for t in topics:
            if isinstance(t, str):
                s = t.strip().strip('",•').replace('",', '')
                if s:
                    cleaned.append(s)
        return cleaned

    def _to_enum_level(self, raw: str) -> CoverageLevel:
        """
        Map chuỗi level sang CoverageLevel theo hệ INSUFFICIENT/PARTIAL/ADEQUATE/COMPREHENSIVE.
        Chấp nhận cả hệ developing/good/excellent/outstanding và quy về hệ của bạn.
        """
        v = (raw or "").strip().lower()

        synonyms = {
            # Hệ của bạn
            "insufficient": "insufficient",
            "partial": "partial",
            "adequate": "adequate",
            "comprehensive": "comprehensive",
            # Hệ 4 mức khác
            "developing": "partial",
            "good": "adequate",
            "excellent": "comprehensive",
            "outstanding": "comprehensive",
        }
        key = synonyms.get(v, v)

        # Match theo value trước rồi đến name
        for e in CoverageLevel:
            if str(getattr(e, "value", "")).lower() == key:
                return e
        for e in CoverageLevel:
            if str(getattr(e, "name", "")).lower() == key:
                return e

        # Fallback an toàn
        return CoverageLevel.INSUFFICIENT

    def _score_to_level(self, score: float) -> CoverageLevel:
        """Convert numeric score → CoverageLevel theo hệ của bạn."""
        if score >= 0.9:
            return CoverageLevel.COMPREHENSIVE
        elif score >= 0.7:
            return CoverageLevel.ADEQUATE
        elif score >= 0.4:
            return CoverageLevel.PARTIAL
        else:
            return CoverageLevel.INSUFFICIENT

    def _fallback_assessment(self, subtopics: List[str], score: float = 0.0) -> CoverageAssessment:
        """Fallback assessment khi LLM/parse thất bại (giữ heuristic score nếu có)."""
        return CoverageAssessment(
            level=CoverageLevel.INSUFFICIENT,
            score=score,
            missing_topics=subtopics,
            covered_topics=[],
        )

    # -----------------------------
    # Stats & config
    # -----------------------------
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
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
        """Reset performance counters."""
        self.fast_decisions = 0
        self.llm_calls = 0

    def configure_thresholds(self, high_confidence: float = None, low_confidence: float = None):
        """Tune ngưỡng quyết định fast path."""
        if high_confidence is not None:
            self.high_confidence_threshold = high_confidence
        if low_confidence is not None:
            self.low_confidence_threshold = low_confidence
        self.logger.info(f"Thresholds updated: high={self.high_confidence_threshold}, low={self.low_confidence_threshold}")

import json
import random
import logging
from urllib.parse import urlparse
from typing import List
from modules.rag_module.datatypes.SearchResult import SearchResult

class FinalLinkSelectorAgent:
    def __init__(self, llm_client):
        self.llm = llm_client
        self.logger = logging.getLogger(__name__)

    def run(self, top_results: List[SearchResult], user_input: str,
            criteria: str, top_k: int = 3) -> List[SearchResult]:

        unique_results = self._remove_duplicates(top_results[:5])
        results_for_llm = []

        for i, result in enumerate(unique_results):
            results_for_llm.append({
                "id": i + 1,
                "title": result.title,
                "snippet": result.snippet[:300] + "..." if len(result.snippet) > 300 else result.snippet,
                "domain": urlparse(result.url).netloc,
                "url": result.url
            })

        prompt = f"""
            Bạn là một thành viên hội đồng chuyên gia giáo dục, đóng vai trò giám khảo trong việc lựa chọn các tài liệu giảng dạy xuất sắc nhất. 
            Từ {len(unique_results)} ứng viên là các tài liệu xuất sắc này, hãy chọn {top_k} tài liệu TỐT NHẤT.

            YÊU CẦU NGƯỜI DÙNG: "{user_input}"
            TIÊU CHÍ CHÍNH: "{criteria}"

            ## TIÊU CHÍ ĐÁNH GIÁ (Tổng điểm: 100%)
            1. **Độ phong phú nội dung (30%)**  
            - Bao gồm nhiều ý, nhiều khía cạnh liên quan đến chủ đề  
            - Có ví dụ, hình ảnh minh họa, bài tập hoặc diễn giải đa chiều
            2. **Tính chuyên sâu (30%)**  
            - Đào sâu khái niệm cốt lõi, giải thích bản chất, tránh hời hợt  
            - Có thể trình bày các cấp độ tư duy (nhận biết → vận dụng → phân tích)
            3. **Tính thực tiễn (25%)**  
            - Gắn với ứng dụng, tình huống thực tế, lớp học thật  
            - Dễ áp dụng bởi giáo viên trong giảng dạy
            4. **Tính cập nhật (15%)**  
            - Sử dụng thông tin, phương pháp, ví dụ gần đây (tính đến thời điểm hiện tại)  
            - Tránh nội dung lạc hậu hoặc không còn phù hợp
            5. **Tính độc đáo (5%)**  
            - Có góc nhìn mới, cách trình bày sáng tạo hoặc tiếp cận khác biệt  
            - Không trùng lặp máy móc với nội dung phổ biến

            ## LOẠI BỎ NGAY:
            - Bất kỳ tài liệu nào có các đặc điểm sau **phải bị loại khỏi danh sách xem xét**:
            - Chỉ là tập hợp bài tập, đề thi hoặc nhiều chủ đề rời rạc
            - Nội dung quá sơ sài, thiếu trọng tâm
            - Không liên quan đến chủ đề đã yêu cầu
            - Lỗi thời, sai kiến thức hoặc không phù hợp với chương trình hiện hành

            ## DANH SÁCH ỨNG VIÊN:
            {json.dumps(results_for_llm, ensure_ascii=False, indent=2)}

            Trả về JSON:
            {{
              "final_selection": [...],
              "selection_summary": "..."
            }}

            CHỈ TRẢ JSON, KHÔNG GIẢI THÍCH GÌ THÊM
        """

        try:
            result = self.llm.call(prompt, temperature=0.3).strip()

            if result.startswith("```json"):
                result = result.removeprefix("```json").removesuffix("```").strip()
            elif result.startswith("```"):
                result = result.removeprefix("```").removesuffix("```").strip()

            data = json.loads(result)
            selected_results = []

            for selection in data.get("final_selection", []):
                idx = selection["id"] - 1
                if 0 <= idx < len(unique_results):
                    r = unique_results[idx]
                    r.final_rank = selection.get("final_rank", 0)
                    r.llm_reasoning = selection.get("why_chosen", "")
                    r.strengths = selection.get("strengths", [])
                    r.detailed_scores = {
                        'content_richness': selection.get("content_richness_score", 0),
                        'practical_value': selection.get("practical_value_score", 0),
                        'depth': selection.get("depth_score", 0),
                        'freshness': selection.get("freshness_score", 0),
                        'uniqueness': selection.get("uniqueness_score", 0)
                    }
                    r.snippet_analysis = selection.get("snippet_analysis", "")
                    selected_results.append(r)

            return sorted(selected_results, key=lambda x: x.final_rank)

        except Exception as e:
            self.logger.error(f"[FinalLinkSelectorAgent] Lỗi LLM: {e}")
            fallback = random.sample(unique_results, min(len(unique_results), top_k))
            return fallback

    def _remove_duplicates(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicate content based on semantic similarity (naive version)"""
        seen = set()
        unique = []
        for r in results:
            key = (r.title.strip().lower(), r.snippet.strip().lower())
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique
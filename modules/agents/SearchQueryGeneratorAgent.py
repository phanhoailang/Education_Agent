import json
import logging
from typing import List, Tuple

class SearchQueryGeneratorAgent:
    def __init__(self, llm_client):
        self.llm = llm_client
        self.logger = logging.getLogger(__name__)

    def run(self, user_input: str) -> Tuple[str, str, List[str], str, List[str], List[str]]:
        prompt = f"""
            Bạn là chuyên gia tìm kiếm tài liệu giáo dục Việt Nam.  
            Nhiệm vụ của bạn là phân tích yêu cầu người dùng và xây dựng một chiến lược tìm kiếm thông minh, chính xác và có chọn lọc.

            Input: "{user_input}"

            Hãy suy luận yêu cầu và trả về JSON với format:
            {{
              "search_query": "query chính tối ưu",
              "alternative_queries": ["query phụ 1", "query phụ 2", "query phụ 3"],
              "selection_criteria": "tiêu chí lựa chọn cụ thể và chi tiết",
              "content_type": "loại nội dung mong muốn",
              "quality_indicators": ["chỉ số chất lượng 1", "chỉ số chất lượng 2"],
              "avoid_patterns": ["pattern tránh 1", "pattern tránh 2"]
            }}

            QUY TẮC QUAN TRỌNG:
            1. Tìm kiếm nội dung CHỦ ĐỀ CỤ THỂ - không chấp nhận tài liệu tổng quát
            2. Ưu tiên tài liệu giảng dạy, giáo án, bài giảng chi tiết
            3. Tránh sách bài tập,giải bài tập, đề thi, tổng hợp nhiều chủ đề
            4. Tìm nội dung có độ sâu, phân tích cụ thể từng khía cạnh

            PHÂN TÍCH NGỮ CẢNH:
            - Nếu là bài học cụ thể: tìm giáo án, slide, lý thuyết
            - Nếu là chủ đề rộng: tìm tài liệu tổng hợp, sơ đồ tư duy
            - Nếu là bài tập: tìm đề bài, lời giải chi tiết
            - Nếu là phương pháp: tìm hướng dẫn, kinh nghiệm thực tế

            NGUỒN UY TÍN:
            - Cao: vietjack.com, loigiaihay.com, *.edu.vn, *.gov.vn
            - Trung bình: violet.vn, hoc247.net, toanmath.com
            - Thấp: blog cá nhân, diễn đàn không kiểm duyệt

            LƯU Ý:
            - Chỉ được trả về json và không được giải thích gì thêm
            - Phải suy luận và trả về các thông tin cần thiết trong json, không được dể trống
            - Hạn chế hoặc trừ điểm mạnh các nội dung chứa các từ khoá như: ngắn nhất, gọn nhất, nhanh nhất
        """

        try:
            result = self.llm.call(prompt, temperature=0.1).strip()

            if result.startswith("```json"):
                result = result.removeprefix("```json").removesuffix("```").strip()
            elif result.startswith("```"):
                result = result.removeprefix("```").removesuffix("```").strip()

            data = json.loads(result)

            return (
                data.get("search_query", user_input),
                data.get("selection_criteria", ""),
                data.get("alternative_queries", []),
                data.get("content_type", ""),
                data.get("quality_indicators", []),
                data.get("avoid_patterns", [])
            )
        except Exception as e:
            self.logger.error(f"[SearchQueryGeneratorAgent] Lỗi khi sinh truy vấn: {e}")
            return user_input, "", [], "", [], []
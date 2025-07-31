import json
import re
import logging

class SubtopicGeneratorAgent:
    def __init__(self, llm):
        self.llm = llm
        self.prompt = """
        Bạn là chuyên gia phân tích giáo dục với kinh nghiệm thiết kế chương trình học.
        Phân tích yêu cầu và xác định các chủ đề con cần thiết để đảm bảo nội dung học tập đầy đủ.

        Yêu cầu: "{request}"

        QUY TRÌNH PHÂN TÍCH:
        1. Xác định lĩnh vực kiến thức, đối tượng học viên, mục tiêu học tập
        2. Chia nhỏ thành các module logic theo thứ tự từ cơ bản đến nâng cao
        3. Đảm bảo tính đầy đủ: bao phủ lý thuyết, thực hành, ứng dụng
        4. Kiểm tra tính liên kết giữa các chủ đề

        TIÊU CHÍ CHẤT LƯỢNG:
        - Mỗi chủ đề rõ ràng, cụ thể, có thể đo lường
        - Tuân thủ nguyên tắc từ đơn giản đến phức tạp
        - Đảm bảo tính thực tiễn và khả năng áp dụng
        - Mỗi chủ đề không quá 8 từ, tối đa 10 chủ đề con

        Trả về JSON array:
        ```json
        [
            "Tên chủ đề con 1",
            "Tên chủ đề con 2"
        ]
        ```

        CHỈ trả về JSON hợp lệ, không thêm văn bản khác.
    """
        self.logger = logging.getLogger(__name__)

    def run(self, user_request: str) -> list[str]:
        prompt = self.prompt.format(request=user_request)
        messages = [{"role": "user", "content": prompt}]

        try:
            content = self.llm.chat(messages, temperature=0.3, max_tokens=500)
            try:
                clean_content = re.sub(r"```json|```", "", content).strip()
                subtopics = json.loads(clean_content)
                if isinstance(subtopics, list):
                    return [str(t).strip().strip('",•').replace('",', '')
                            for t in subtopics if t.strip()][:10]
            except json.JSONDecodeError:
                lines = content.split("\n")
                return [line.strip('-•1234567890. \"[]')
                        for line in lines if line.strip()][:10]
        except Exception as e:
            self.logger.error(f"Subtopic extraction failed: {e}")
            return []

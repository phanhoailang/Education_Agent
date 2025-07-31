from utils.GPTClient import GPTClient
from utils.GeminiClient import GeminiClient
from typing import Dict, Any

class LessonPlanOutlineAgent:
    def __init__(self, llm: GPTClient):
    # def __init__(self, llm: GeminiClient):
        self.llm = llm
        self.system_prompt = """
            Bạn là một chuyên gia giáo dục Việt Nam, thành thạo chương trình giáo dục phổ thông 2018 từ Tiểu học đến THPT. Nhiệm vụ của bạn là tạo ra **khung kế hoạch bài giảng** (outline) hoàn chỉnh, chi tiết, phù hợp với chuẩn giáo dục Việt Nam.

            PHÂN TÍCH VÀ XỬ LÝ:
            1. **Xác định thông tin cơ bản:**
            - Môn học và cấp học
            - Độ tuổi học sinh
            - Bộ sách giáo khoa (nếu có)
            - Phong cách dạy học (truyền thống, tích cực, STEM...)
            -  Thời lượng bài học và số tiết: 1 tiết = 40-45 phút. Nếu >60 phút thì chia thành nhiều tiết. Ví dụ: 45 phút = 1 tiết, 90 phút = 2 tiết,...

            2. **Phân tích mục tiêu học tập:**
            - Kiến thức cần đạt
            - Kỹ năng cần rèn luyện  
            - Phẩm chất và năng lực cần phát triển
            - Mức độ Bloom (nhận biết, thông hiểu, vận dụng, phân tích, đánh giá, sáng tạo)

            KHUNG KẾ HOẠCH BÀI GIẢNG OUTPUT:

            #### I. THÔNG TIN CHUNG
            - **Môn học:** [Tên môn]
            - **Lớp:** [Khối lớp]
            - **Bài học:** [Tên bài/chủ đề]
            - **Thời lượng:** [X phút (Y tiết)]
            - **Bộ sách:** [Tên bộ sách nếu có]
            - **Phong cách:** [Truyền thống/Tích cực/Khác]

            #### II. MỤC TIÊU BÀI HỌC
            **A. Kiến thức:**
            - [Mục tiêu kiến thức cụ thể]
            - [Khái niệm, định lý, sự kiện cần nắm]

            **B. Kỹ năng:**
            - [Kỹ năng thực hành, tư duy, giao tiếp...]
            - [Kỹ năng vận dụng kiến thức]

            **C. Phẩm chất & Năng lực:**
            - [Năng lực chung: tự học, giải quyết vấn đề, giao tiếp...]
            - [Phẩm chất: yêu nước, trách nhiệm, chăm chỉ...]
            - [Năng lực đặc thù của môn học]

            #### III. CHUẨN BỊ
            **A. Của giáo viên:**
            - Tài liệu: [SGK, tài liệu tham khảo, bài tập]
            - Thiết bị: [Máy chiếu, bảng, đồ dùng thí nghiệm...]
            - Phương pháp: [PPDH chính được sử dụng]

            **B. Của học sinh:**
            - Dụng cụ: [Sách vở, dụng cụ học tập cần thiết]
            - Kiến thức: [Bài cũ cần ôn tập, kiến thức liên quan]

            #### IV. TIẾN TRÌNH DẠY HỌC

            **A. KHỞI ĐỘNG (X phút)**
            - Mục tiêu: [Tạo hứng thú, gắn kết kiến thức cũ-mới]
            - Hoạt động: [Trò chơi, câu hỏi, tình huống thực tế...]
            - Sản phẩm: [Phản hồi, thảo luận, nhận thức vấn đề]

            **B. HÌNH THÀNH KIẾN THỨC (X phút)**
            - Mục tiêu: [Khám phá, xây dựng kiến thức mới]
            - Hoạt động chính:
            + Hoạt động 1: [Quan sát, thí nghiệm, đọc tài liệu...]
            + Hoạt động 2: [Thảo luận, phân tích, so sánh...]
            + Hoạt động 3: [Tổng hợp, khái quát hóa...]
            - Sản phẩm: [Kiến thức mới được xây dựng]

            **C. LUYỆN TẬP (X phút)**
            - Mục tiêu: [Củng cố, thực hành kiến thức vừa học]
            - Hoạt động:
            + Bài tập cơ bản: [Áp dụng trực tiếp]
            + Bài tập nâng cao: [Tư duy, phân tích]
            - Sản phẩm: [Bài giải, trình bày, thảo luận]

            **D. VẬN DỤNG/MỞ RỘNG (X phút)**
            - Mục tiêu: [Áp dụng vào thực tế, tình huống mới]
            - Hoạt động: [Tình huống thực tế, dự án nhỏ, nghiên cứu...]
            - Sản phẩm: [Giải pháp, ý tưởng, kế hoạch hành động]

            #### V. ĐÁNH GIÁ
            **A. Đánh giá quá trình:**
            - [Quan sát tham gia, thảo luận]
            - [Hoạt động nhóm, cá nhân]

            **B. Đánh giá kết quả:**
            - [Câu hỏi kiểm tra, bài tập]
            - [Tiêu chí cụ thể cho từng mức độ]

            #### VI. GỢI Ý PHƯƠNG PHÁP & CÔNG CỤ
            - **Phương pháp chính:** [Phù hợp cấp học và môn học]
            - **Kỹ thuật dạy học:** [Brainstorming, jigsaw, role-play...]
            - **Công nghệ hỗ trợ:** [App, website, phần mềm nếu phù hợp]
            - **Trò chơi học tập:** [Nếu phù hợp với độ tuổi]

            QUY TẮC OUTPUT:
            - Trả lời bằng tiếng Việt
            - Chia rõ từng phần với header rõ ràng
            - Ngắn gọn, súc tích - làm "khung sườn" cho bước tiếp theo
            - Đảm bảo logic giáo dục và phù hợp lứa tuổi
            - Thời gian các hoạt động phải hợp lý và tổng bằng thời lượng bài học
        """

    def run(self, user_prompt: str) -> str:
        """
        Tạo khung kế hoạch bài giảng từ yêu cầu người dùng
        """
        try:
            print(f"🔄 Đang gọi LLM để tạo outline...")
            
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"YÊU CẦU ĐẦU VÀO:\n{user_prompt}"}
            ]
            
            response = self.llm.chat(messages, temperature=0.7)
            
            print(f"✅ LLM đã trả về outline ({len(response)} ký tự)")
            print("📄 OUTLINE CONTENT:")
            print("-" * 40)
            print(response)
            print("-" * 40)
            
            return response
                
        except Exception as e:
            error_msg = f"Lỗi khi tạo outline: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg
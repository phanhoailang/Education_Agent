from utils.GPTClient import GPTClient
from utils.GeminiClient import GeminiClient
from typing import Dict, Any, List

class LessonContentWriterAgent:
    def __init__(self, llm: GPTClient):
    # def __init__(self, llm: GeminiClient):
        self.llm = llm
        self.system_prompt = """
            Bạn là giáo viên chuyên nghiệp, nhiều kinh nghiệm giảng dạy theo chương trình GDPT 2018. Nhiệm vụ của bạn là viết nội dung chi tiết cho từng phần cụ thể trong kế hoạch bài giảng.

            YÊU CẦU VIẾT CHI TIẾT:

            #### 1. PHÂN TÍCH CONTEXT
            - Xác định vị trí của phần này trong tổng thể bài học
            - Nắm rõ mục tiêu cụ thể cần đạt
            - Hiểu đặc điểm tâm lý lứa tuổi

            #### 2. CẤU TRÚC NỘI DUNG

            **A. NẾU LÀ PHẦN "KHỞI ĐỘNG":**
            - **Hoạt động mở đầu:** [Tình huống thực tế, trò chơi, câu hỏi gây tò mò]
            - **Kết nối kiến thức cũ:** [Ôn tập nhanh kiến thức liên quan]
            - **Định hướng bài mới:** [Đặt vấn đề, tạo động cơ học tập]
            - **Thời gian:** X phút
            - **Phương pháp:** [Đàm thoại, trực quan, trò chơi...]

            **B. NẾU LÀ PHẦN "HÌNH THÀNH KIẾN THỨC":**
            - **Kiến thức cốt lõi:** [Trình bày rõ ràng, có logic]
            - **Ví dụ minh họa:** [Cụ thể, gần gũi với học sinh]
            - **Hoạt động khám phá:** [Thí nghiệm, quan sát, đọc hiểu, thảo luận]
            - **Câu hỏi định hướng:** [Dẫn dắt tư duy học sinh]
            - **Sơ đồ/Bảng tóm tắt:** [Nếu cần thiết]

            **C. NẾU LÀ PHẦN "LUYỆN TẬP":**
            - **Bài tập mức độ 1:** [Áp dụng trực tiếp]
            - **Bài tập mức độ 2:** [Vận dụng có biến đổi]
            - **Bài tập mức độ 3:** [Tư duy phân tích, tổng hợp]
            - **Hướng dẫn giải:** [Phương pháp, các bước thực hiện]
            - **Xử lý sai lầm:** [Dự đoán và sửa lỗi thường gặp]

            **D. NẾU LÀ PHẦN "VẬN DỤNG/MỞ RỘNG":**
            - **Tình huống thực tế:** [Áp dụng kiến thức vào đời sống]
            - **Dự án mini:** [Nghiên cứu, sáng tạo]
            - **Câu hỏi mở rộng:** [Kích thích tư duy sáng tạo]
            - **Kết nối liên môn:** [Nếu phù hợp]

            #### 3. YẾU TỐ BẮT BUỘC
            - **Tương tác học sinh:** Câu hỏi, hoạt động nhóm, thảo luận
            - **Đánh giá quá trình:** Quan sát, phản hồi tức thì
            - **Phù hợp lứa tuổi:** Ngôn ngữ, ví dụ, hoạt động
            - **Tích hợp công nghệ:** Nếu phù hợp và có sẵn thiết bị
            - **Kết nối thực tế:** Ví dụ từ cuộc sống, địa phương

            #### 4. ĐỊNH DẠNG OUTPUT
            - **Hoạt động của GV:** [Làm gì, nói gì]
            - **Hoạt động của HS:** [Phản hồi, thực hiện nhiệm vụ]
            - **Tài liệu/thiết bị:** [Cần sử dụng gì]
            - **Thời gian:** [Phân bổ cụ thể]
            - **Đánh giá:** [Cách nhận biết HS đã đạt mục tiêu]

            QUY TẮC VIẾT:
            - Viết bằng tiếng Việt, rõ ràng, cụ thể
            - Có thể copy trực tiếp vào giáo án để sử dụng
            - Đảm bảo tính khoa học và sư phạm
            - Phù hợp với chương trình và SGK Việt Nam
            - Tránh lan man, tập trung vào mục tiêu của phần
            - Bao gồm cả hoạt động dự phòng nếu có thời gian thừa
        """

    def run(self, section_name: str, outline: str, chunks: List[Dict], mon_hoc: str = "", lop: str = "", ten_bai: str = "") -> str:
        """
        Viết nội dung chi tiết cho một phần cụ thể của bài giảng
        """
        try:
            print(f"🔄 Đang gọi LLM để viết phần {section_name}...")
            
            # Chuẩn bị context từ chunks
            chunks_content = ""
            if chunks:
                chunks_content = "\n".join([
                    f"Chunk {i+1}: {chunk.get('content', '')[:500]}..."
                    for i, chunk in enumerate(chunks[:3])  # Chỉ lấy 3 chunks đầu
                ])
            
            # Tạo prompt
            prompt = f"""
                THÔNG TIN ĐẦU VÀO:
                **Môn học:** {mon_hoc}
                **Lớp:** {lop}
                **Bài học:** {ten_bai}
                **Phần cần viết:** {section_name}

                **Khung outline tổng thể:**
                {outline}

                **Tài liệu tham khảo:**
                {chunks_content}

                Hãy viết nội dung chi tiết cho phần "{section_name}" theo đúng mục tiêu và yêu cầu.
            """

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            response = self.llm.chat(messages, temperature=0.7)
            
            print(f"✅ LLM đã trả về nội dung phần {section_name} ({len(response)} ký tự)")
            print(f"📄 CONTENT PREVIEW ({section_name}):")
            print("-" * 30)
            preview = response[:300] + "..." if len(response) > 300 else response
            print(preview)
            print("-" * 30)
            
            return response
                
        except Exception as e:
            error_msg = f"Lỗi khi viết nội dung: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg
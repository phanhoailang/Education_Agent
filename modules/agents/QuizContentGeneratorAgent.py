from utils.GPTClient import GPTClient
from utils.GeminiClient import GeminiClient
from typing import Dict, Any, List

class QuizContentGeneratorAgent:
    def __init__(self, llm: GPTClient):
    # def __init__(self, llm: GeminiClient):
        self.llm = llm
        self.system_prompt = """
            Bạn là giáo viên chuyên nghiệp, nhiều kinh nghiệm ra đề kiểm tra theo chương trình GDPT 2018. Nhiệm vụ của bạn là tạo câu hỏi trắc nghiệm chi tiết cho từng mức độ tư duy cụ thể.

            YÊU CẦU TẠO CÂU HỎI CHI TIẾT:

            #### 1. PHÂN TÍCH YÊU CẦU
            - Xác định mức độ tư duy cần tạo câu hỏi
            - Nắm rõ nội dung kiến thức cần kiểm tra
            - Hiểu đặc điểm tâm lý lứa tuổi học sinh

            #### 2. CẤU TRÚC CÂU HỎI

            **A. NẾU LÀ MỨC ĐỘ "NHẬN BIẾT":**
            - **Đặc điểm:** Kiểm tra khả năng nhớ lại kiến thức cơ bản
            - **Dạng câu hỏi:** Định nghĩa, khái niệm, sự kiện, công thức
            - **Từ khóa thường dùng:** "Gì là...", "Định nghĩa nào đúng", "Công thức nào", "Đặc điểm của..."
            - **Ví dụ mẫu:** "Công thức tính diện tích hình tròn là:"

            **B. NẾU LÀ MỨC ĐỘ "THÔNG HIỂU":**
            - **Đặc điểm:** Kiểm tra khả năng hiểu và giải thích kiến thức
            - **Dạng câu hỏi:** So sánh, phân loại, giải thích, mô tả mối quan hệ
            - **Từ khóa thường dùng:** "Tại sao...", "Điểm khác biệt", "Mối quan hệ", "Giải thích..."
            - **Ví dụ mẫu:** "Tại sao nước ở trạng thái lỏng ở nhiệt độ phòng?"

            **C. NẾU LÀ MỨC ĐỘ "VẬN DỤNG":**
            - **Đặc điểm:** Áp dụng kiến thức vào tình huống quen thuộc
            - **Dạng câu hỏi:** Bài tập tính toán, áp dụng công thức, giải quyết vấn đề cơ bản
            - **Từ khóa thường dùng:** "Tính...", "Xác định...", "Trong trường hợp...", "Áp dụng..."
            - **Ví dụ mẫu:** "Tính diện tích hình tròn có bán kính 5cm"

            **D. NẾU LÀ MỨC ĐỘ "VẬN DỤNG CAO":**
            - **Đặc điểm:** Phân tích, tổng hợp, đánh giá, sáng tạo
            - **Dạng câu hỏi:** Tình huống phức tạp, phân tích, so sánh, đánh giá
            - **Từ khóa thường dùng:** "Phân tích...", "Đánh giá...", "So sánh...", "Dự đoán..."
            - **Ví dụ mẫu:** "Phân tích ảnh hưởng của việc tăng nhiệt độ đến tốc độ phản ứng"

            #### 3. TIÊU CHUẨN KỸ THUẬT

            **A. Cấu trúc mỗi câu hỏi:**
            ```
            **Câu X:** [Đề bài rõ ràng, ngắn gọn]
            A. [Đáp án 1]
            B. [Đáp án 2] 
            C. [Đáp án 3]
            D. [Đáp án đúng]

            *Đáp án: D*
            *Giải thích: [Lý do tại sao D đúng và các đáp án khác sai]*
            ```

            **B. Yêu cầu về đáp án:**
            - **Đáp án đúng:** Chính xác 100%, không gây tranh cãi
            - **Đáp án nhiễu:** Hợp lý, có tính đánh lừa, không quá dễ loại trừ
            - **Độ dài tương đương:** Các lựa chọn có độ dài gần bằng nhau
            - **Tránh mẫu:** Đáp án đúng không có mẫu cố định (luôn là A, B, C hoặc D)

            **C. Ngôn ngữ và trình bày:**
            - Phù hợp với lứa tuổi học sinh
            - Tránh từ ngữ mơ hồ như "có thể", "thường", "hầu hết"
            - Sử dụng thuật ngữ chính xác theo SGK
            - Câu hỏi không quá dài, dễ hiểu

            #### 4. QUY TRÌNH TẠO CÂU HỎI

            **Bước 1:** Xác định kiến thức cụ thể cần kiểm tra
            **Bước 2:** Tạo đề bài phù hợp với mức độ tư duy
            **Bước 3:** Tạo đáp án đúng chính xác
            **Bước 4:** Tạo 3 đáp án nhiễu hợp lý
            **Bước 5:** Viết giải thích ngắn gọn
            **Bước 6:** Kiểm tra tính khoa học và sư phạm

            #### 5. TRÁNH CÁC LỖI THƯỜNG GẶP
            - Câu hỏi quá dễ đoán đáp án
            - Đáp án nhiễu không hợp lý
            - Sử dụng "Tất cả đều đúng" hoặc "Không có đáp án nào đúng"
            - Câu hỏi có nhiều đáp án đúng
            - Thông tin trong câu này tiết lộ đáp án câu khác
            - Ngôn ngữ không phù hợp lứa tuổi

            #### 6. ĐỊNH DẠNG OUTPUT
            - Mỗi câu hỏi một khối rõ ràng
            - Đánh số thứ tự liên tục
            - Có đáp án và giải thích cho mỗi câu
            - Sắp xếp đáp án ngẫu nhiên (không theo mẫu cố định)

            QUY TẮC TẠO:
            - Viết bằng tiếng Việt, rõ ràng, cụ thể
            - Đảm bảo tính khoa học và chính xác
            - Phù hợp với chương trình và SGK Việt Nam
            - Tạo đủ số lượng câu theo yêu cầu outline
            - Đảm bảo độ phân biệt cao giữa các mức độ
            - Câu hỏi có tính ứng dụng thực tế khi phù hợp
        """

    def run(self, question_type: str, outline: str, chunks: List[Dict], mon_hoc: str = "", lop: str = "", chu_de: str = "", so_cau: str = "20") -> str:
        """
        Tạo câu hỏi trắc nghiệm chi tiết cho một mức độ tư duy cụ thể
        """
        try:
            print(f"🔄 Đang gọi LLM để tạo câu hỏi {question_type}...")
            
            # Chuẩn bị context từ chunks
            chunks_content = ""
            if chunks:
                chunks_content = "\n".join([
                    f"Chunk {i+1}: {chunk.get('content', '')[:500]}..."
                    for i, chunk in enumerate(chunks[:3])  # Chỉ lấy 3 chunks đầu
                ])
            
            # Xác định số câu cho mỗi loại dựa trên outline và tổng số câu
            try:
                total_questions = int(so_cau)
            except:
                total_questions = 20
                
            # Phân bổ câu hỏi theo mức độ (có thể điều chỉnh theo outline)
            question_distribution = {
                "NHẬN BIẾT": max(1, int(total_questions * 0.25)),      # 25%
                "THÔNG HIỂU": max(1, int(total_questions * 0.35)),      # 35%
                "VẬN DỤNG": max(1, int(total_questions * 0.30)),        # 30%
                "VẬN DỤNG CAO": max(1, int(total_questions * 0.10))     # 10%
            }
            
            questions_for_this_type = question_distribution.get(question_type, 3)
            
            # Tạo prompt
            prompt = f"""
                THÔNG TIN ĐẦU VÀO:
                **Môn học:** {mon_hoc}
                **Lớp:** {lop}
                **Chủ đề:** {chu_de}
                **Mức độ cần tạo:** {question_type}
                **Số câu cần tạo:** {questions_for_this_type} câu

                **Khung outline tổng thể:**
                {outline}

                **Tài liệu tham khảo:**
                {chunks_content}

                Hãy tạo {questions_for_this_type} câu hỏi trắc nghiệm mức độ "{question_type}" theo đúng yêu cầu và chuẩn mực đã nêu. 
                
                LÚU Ý QUAN TRỌNG:
                - Đánh số câu hỏi bắt đầu từ câu 1 (sẽ được đánh số lại sau)
                - Mỗi câu phải có đầy đủ: đề bài, 4 lựa chọn A-B-C-D, đáp án đúng, giải thích
                - Đảm bảo đáp án đúng được phân bố ngẫu nhiên trong A, B, C, D
                - Nội dung phải sát với tài liệu tham khảo và phù hợp với lứa tuổi
            """

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            response = self.llm.chat(messages, temperature=0.8)
            
            print(f"✅ LLM đã trả về câu hỏi {question_type} ({len(response)} ký tự)")
            print(f"📄 QUESTIONS PREVIEW ({question_type}):")
            print("-" * 30)
            preview = response[:400] + "..." if len(response) > 400 else response
            print(preview)
            print("-" * 30)
            
            return response
                
        except Exception as e:
            error_msg = f"Lỗi khi tạo câu hỏi: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg
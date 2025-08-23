from typing import Dict, Any
import re
from utils.GPTClient import GPTClient

class SlideOutlineAgent:
    def __init__(self, llm: GPTClient):
        self.llm = llm
        self.system_prompt = """
Bạn là chuyên gia tạo nội dung slide giáo dục. Nhiệm vụ của bạn là chuyển đổi lesson plan thành sườn nội dung slide đơn giản, rõ ràng.

NGUYÊN TẮC TẠO SLIDE CONTENT:
1. Mỗi slide tập trung 1 ý chính
2. Nội dung ngắn gọn (tối đa 6-8 dòng/slide)
3. Sử dụng bullet points, dễ đọc
4. Cấu trúc logic từ cơ bản đến nâng cao
5. Phù hợp với đối tượng học sinh

FORMAT OUTPUT YÊU CẦU:

```
=== SLIDE [SỐ]: [TIÊU ĐỀ SLIDE] ===
[Nội dung slide dưới dạng bullet points hoặc đoạn văn ngắn]

Ghi chú: [Ghi chú cho giáo viên nếu cần]
---
```

CẤU TRÚC SLIDE CHUẨN:
- Slide 1: Title slide (tiêu đề bài + thông tin cơ bản)
- Slide 2: Mục tiêu bài học 
- Slide 3-4: Kiến thức cũ/Khởi động
- Slide 5-N: Nội dung chính (chia nhỏ từng phần)
- Slide N+1: Thực hành/Ví dụ minh họa
- Slide N+2: Tóm tắt/Kết luận
- Slide cuối: Bài tập về nhà/Q&A

QUY TẮC NỘI DUNG:
- Tiếng Việt rõ ràng, dễ hiểu
- Mỗi slide 3-6 bullet points
- Tránh văn bản dài
- Có emoji phù hợp để sinh động
- Gợi ý hình ảnh/biểu đồ nếu cần

TỔNG SỐ SLIDE: 8-12 slide cho 1 bài học 45 phút
        """.strip()

    def run(self, lesson_plan_content: str, user_requirements: str = "") -> str:
        """
        Tạo sườn nội dung slide từ lesson plan
        """
        try:
            print("🔄 Đang tạo sườn nội dung slide...")

            prompt_content = f"""
KẾ HOẠCH BÀI HỌC:
{lesson_plan_content}

YÊU CẦU BỔ SUNG TỪ NGƯỜI DÙNG:
{user_requirements or "Không có yêu cầu đặc biệt"}

NHIỆM VỤ: 
Hãy tạo SƯỜN NỘI DUNG cho từng slide dựa trên lesson plan trên. 
Tập trung vào việc chia nhỏ nội dung thành các slide logic, mỗi slide có nội dung cụ thể.

YÊU CẦU OUTPUT:
- Sử dụng format: === SLIDE [SỐ]: [TIÊU ĐỀ] ===
- Nội dung mỗi slide dưới dạng bullet points
- Ghi chú hướng dẫn cho giáo viên (nếu cần)
- Tổng cộng 8-12 slide
- Ngôn ngữ Tiếng Việt
"""

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt_content}
            ]
            
            response = self.llm.chat(messages, temperature=0.7)

            # Post-process để đảm bảo format chuẩn
            processed_response = self._format_slide_content(response)

            print(f"✅ Đã tạo sườn nội dung cho {self._count_slides(processed_response)} slides")
            return processed_response

        except Exception as e:
            error_msg = f"Lỗi khi tạo sườn slide: {str(e)}"
            print(f"❌ {error_msg}")
            return error_msg
        except KeyboardInterrupt:
            print("⏹️ Người dùng đã hủy quá trình tạo slide.")
            return "Quá trình tạo slide đã bị hủy."
    
    def _format_slide_content(self, content: str) -> str:
        """
        Đảm bảo format output đúng chuẩn
        """
        # Thêm separator giữa các slide nếu chưa có
        if "---" not in content:
            content = re.sub(r'(=== SLIDE \d+:.*?===\n.*?)(?=\n=== SLIDE|\Z)', 
                           r'\1\n---\n', content, flags=re.DOTALL)
        
        return content.strip()
    
    def _count_slides(self, content: str) -> int:
        """
        Đếm số lượng slide trong content
        """
        return len(re.findall(r'=== SLIDE \d+:', content))

    def get_slide_summary(self, slide_content: str) -> Dict[str, Any]:
        """
        Tạo summary thông tin về slides đã tạo
        """
        slides = re.findall(r'=== SLIDE (\d+): (.*?) ===', slide_content)
        
        return {
            "total_slides": len(slides),
            "slide_titles": [{"number": int(num), "title": title.strip()} 
                           for num, title in slides],
            "estimated_duration": len(slides) * 3,  # ~3 phút/slide
            "content_length": len(slide_content)
        }

# Example usage function
def generate_slide_content_example():
    """
    Ví dụ về cách sử dụng SlideOutlineAgent
    """
    
    # Sample lesson plan
    sample_lesson_plan = """
    Bài học: Giới thiệu về Photosynthesis (Quang hợp)
    Môn: Sinh học lớp 10
    Thời gian: 45 phút
    
    Mục tiêu:
    - Hiểu khái niệm quang hợp
    - Nắm được phương trình quang hợp
    - Biết vai trò của quang hợp với sự sống
    
    Nội dung chính:
    1. Khái niệm quang hợp
    2. Điều kiện xảy ra quang hợp
    3. Phương trình tổng quát
    4. Giai đoạn sáng và giai đoạn tối
    5. Ý nghĩa của quang hợp
    
    Hoạt động: Thí nghiệm đơn giản với lá cây
    Đánh giá: Câu hỏi trắc nghiệm
    """
    
    # Giả lập GPT client (thực tế sẽ dùng GPTClient thật)
    class MockGPTClient:
        def chat(self, messages, temperature=0.7):
            return """
=== SLIDE 1: QUANG HỢP - SỰ SỐNG CỦA THỰC VẬT ===
🌱 **Bài học:** Giới thiệu về Quang hợp (Photosynthesis)
📚 **Môn học:** Sinh học lớp 10
⏰ **Thời gian:** 45 phút
🎯 **Hôm nay chúng ta sẽ khám phá bí mật của sự sống xanh!**

---

=== SLIDE 2: MỤC TIÊU BÀI HỌC ===
Sau bài học này, các em sẽ có thể:

✅ Giải thích được khái niệm quang hợp
✅ Viết được phương trình tổng quát của quang hợp  
✅ Phân tích vai trò quan trọng của quang hợp đối với sự sống
✅ Nhận biết các điều kiện cần thiết cho quang hợp

---

=== SLIDE 3: KHỞI ĐỘNG - TẠI SAO LÁ CÂY MÀU XANH? ===
🤔 **Câu hỏi thảo luận:**
• Tại sao hầu hết lá cây đều có màu xanh?
• Cây cối lấy thức ăn từ đâu?
• Điều gì xảy ra khi cây thiếu ánh sáng?

💡 **Gợi ý:** Hãy quan sát cây trồng trong nhà vs ngoài trời

Ghi chú: Cho HS thảo luận nhóm 3-4 người, 2 phút
---

=== SLIDE 4: KHÁI NIỆM QUANG HỢP ===
🌿 **Quang hợp (Photosynthesis) là:**

• Quá trình thực vật sử dụng ánh sáng mặt trời
• Chuyển đổi CO₂ và H₂O thành glucose (đường)
• Giải phóng O₂ ra môi trường
• Diễn ra chủ yếu ở lá cây (lục lạp)

🔬 **Công thức đơn giản:** Ánh sáng + CO₂ + H₂O → Glucose + O₂

---

=== SLIDE 5: PHƯƠNG TRÌNH TỔNG QUÁT ===
⚗️ **Phương trình hóa học:**

**6CO₂ + 6H₂O + Ánh sáng → C₆H₁₂O₆ + 6O₂**

📝 **Giải thích từng thành phần:**
• **6CO₂:** Khí cacbonic từ không khí
• **6H₂O:** Nước từ rễ cây
• **Ánh sáng:** Năng lượng mặt trời
• **C₆H₁₂O₆:** Glucose (đường đơn)
• **6O₂:** Khí oxi thải ra

Ghi chú: Nhấn mạnh cần học thuộc phương trình này
---

=== SLIDE 6: ĐIỀU KIỆN THỰC HIỆN QUANG HỢP ===
🌞 **4 điều kiện cần thiết:**

1. **Ánh sáng mặt trời** - Nguồn năng lượng chính
2. **Khí CO₂** - Nguyên liệu cacbon  
3. **Nước (H₂O)** - Nguyên liệu hydro
4. **Chất diệp lục** - "Máy móc" thực hiện phản ứng

❌ **Thiếu 1 trong 4 → Không có quang hợp**

---

=== SLIDE 7: HAI GIAI ĐOẠN CỦA QUANG HỢP ===
⚡ **GIAI ĐOẠN SÁNG (Light Reaction):**
• Xảy ra ở tilacoit (lục lạp)
• Cần ánh sáng trực tiếp
• Phân giải H₂O → O₂ + H⁺ + e⁻

🌙 **GIAI ĐOẠN TỐI (Dark Reaction - Calvin Cycle):**
• Xảy ra ở stroma (lục lạp)  
• Không cần ánh sáng trực tiếp
• Tổng hợp glucose từ CO₂

---

=== SLIDE 8: Ý NGHĨA CỦA QUANG HỢP ===
🌍 **Đối với thực vật:**
• Tạo thức ăn (glucose) cho bản thân
• Tạo nguyên liệu xây dựng tế bào

🐾 **Đối với động vật:**
• Nguồn thức ăn gián tiếp (chuỗi thức ăn)
• Cung cấp O₂ để hô hấp

🌱 **Đối với môi trường:**
• Giảm CO₂ trong không khí
• Duy trì cân bằng sinh thái

---

=== SLIDE 9: THÍ NGHIỆM MINH HỌA ===
🔬 **Thí nghiệm đơn giản: Kiểm tra O₂ từ quang hợp**

**Dụng cụ:** Cây thủy sinh + Bình thủy tinh + Ánh sáng
**Cách làm:** 
1. Đặt cây trong bình nước
2. Chiếu sáng bằng đèn
3. Quan sát bọt khí thoát ra

**Kết quả:** Nhiều bọt khí = Nhiều O₂ = Quang hợp mạnh

Ghi chú: Nếu có điều kiện, thực hiện demo ngay trên lớp
---

=== SLIDE 10: TÓM TẮT BÀI HỌC ===
📋 **Những điều cần nhớ:**

✅ Quang hợp = Tạo thức ăn bằng ánh sáng
✅ Phương trình: 6CO₂ + 6H₂O + ánh sáng → C₆H₁₂O₆ + 6O₂  
✅ Cần 4 điều kiện: Ánh sáng, CO₂, H₂O, diệp lục
✅ Có 2 giai đoạn: Sáng và tối
✅ Quan trọng cho tất cả sự sống trên Trái Đất

---

=== SLIDE 11: BÀI TẬP VỀ NHÀ & Q&A ===
📝 **Bài tập về nhà:**
• Bài tập SGK trang 45-46 (câu 1,2,3)
• Quan sát và ghi chép: Sự khác biệt giữa lá cây nơi có ánh sáng và lá ở chỗ tối

❓ **Có câu hỏi gì không?**
📧 **Liên hệ:** [Email giáo viên]

**Bài tiếp theo:** Hô hấp ở thực vật
---
"""
    
    # Test với mock client
    mock_client = MockGPTClient()
    agent = SlideOutlineAgent(mock_client)
    
    result = agent.run(sample_lesson_plan, "Tập trung vào thí nghiệm thực tế")
    
    # Hiển thị summary
    summary = agent.get_slide_summary(result)
    print(f"\n📊 SUMMARY:")
    print(f"Tổng số slides: {summary['total_slides']}")
    print(f"Thời lượng ước tính: {summary['estimated_duration']} phút")
    print(f"Các slide: {[s['title'] for s in summary['slide_titles']]}")
    
    return result

if __name__ == "__main__":
    # Chạy ví dụ
    example_content = generate_slide_content_example()
    print("\n" + "="*50)
    print("SLIDE CONTENT GENERATED:")
    print("="*50)
    print(example_content)

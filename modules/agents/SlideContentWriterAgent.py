from typing import Dict, Any, List, Optional
import json
import re


class SlideContentWriterAgent:
    """
    🎯 Agent tạo sườn nội dung slide từ lesson plan chỉ bằng prompt
    """

    def __init__(self, llm):
        self.llm = llm
        self.system_prompt = """
Bạn là chuyên gia thiết kế nội dung slide giáo dục. Nhiệm vụ: chuyển đổi lesson plan thành sườn nội dung slide cụ thể, chi tiết.

NGUYÊN TẮC THIẾT KẾ SLIDE:
1. Mỗi slide tập trung 1 ý chính
2. Quy tắc 6x6: tối đa 6 bullet points, mỗi bullet ≤ 12 từ
3. Nội dung ngắn gọn, dễ đọc, phù hợp lứa tuổi
4. Có ghi chú cho giáo viên (speaker notes)
5. Gợi ý hình ảnh minh họa khi cần

CẤU TRÚC SLIDE CHUẨN:
- Slide 1: Title slide (tiêu đề + thông tin cơ bản)
- Slide 2-3: Mục tiêu + Khởi động
- Slide 4-N: Nội dung chính (chia nhỏ từng phần)
- Slide N+1: Thực hành/Ví dụ
- Slide N+2: Tóm tắt/Kết luận
- Slide cuối: Q&A/Bài tập về nhà

FORMAT OUTPUT (JSON):
{
  "meta": {
    "title": "Tiêu đề bài học",
    "subject": "Môn học", 
    "grade": "Khối lớp",
    "duration": "Thời lượng",
    "total_slides": "Số slide",
    "tone": "Phong cách"
  },
  "slides": [
    {
      "slide_number": 1,
      "type": "title|content|summary",
      "title": "Tiêu đề slide",
      "subtitle": "Phụ đề (nếu có)",
      "content": [
        "• Bullet point 1",
        "• Bullet point 2",
        "• ..."
      ],
      "speaker_notes": "Ghi chú cho giáo viên nói gì",
      "image_suggestion": "Gợi ý hình ảnh minh họa",
      "layout_type": "title_only|title_and_body|title_and_image"
    }
  ]
}

QUY TẮC:
- Chỉ trả về JSON hợp lệ, KHÔNG có markdown ```json```
- Tiếng Việt rõ ràng, dễ hiểu
- Tổng số slide: 8-15 slide
- Mỗi bullet point ngắn gọn, súc tích
        """.strip()

    def run(
        self,
        lesson_plan: Dict[str, Any],
        user_requirements: str = "",
        style_tone: str = "thân thiện",
        max_slides: int = 15
    ) -> Dict[str, Any]:
        """
        Tạo sườn nội dung slide từ lesson plan
        """
        try:
            print("🎬 Đang tạo sườn nội dung slide...")

            # Extract lesson plan data
            title = lesson_plan.get("title", "Bài học")
            objectives = lesson_plan.get("objectives", [])
            sections = lesson_plan.get("sections", [])
            subject = lesson_plan.get("subject", lesson_plan.get("mon_hoc", ""))
            grade = lesson_plan.get("grade", lesson_plan.get("grade_level", ""))
            duration = lesson_plan.get("duration", "45 phút")

            # Create user prompt
            user_prompt = f"""
THÔNG TIN BÀI HỌC:
- Tiêu đề: {title}
- Môn học: {subject}
- Lớp: {grade}  
- Thời lượng: {duration}
- Phong cách: {style_tone}

MỤC TIÊU BÀI HỌC:
{self._format_objectives(objectives)}

NỘI DUNG CHI TIẾT:
{self._format_sections(sections)}

YÊU CẦU BỔ SUNG:
{user_requirements or "Không có yêu cầu đặc biệt"}

NHIỆM VỤ:
Tạo sườn nội dung chi tiết cho tối đa {max_slides} slides. Mỗi slide phải có:
1. Tiêu đề rõ ràng
2. Nội dung cụ thể (bullet points)
3. Ghi chú cho giáo viên
4. Gợi ý hình ảnh (nếu cần)

Trả về JSON theo format đã chỉ định, KHÔNG có markdown wrapper.
            """.strip()

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            raw_response = self.llm.chat(messages, temperature=0.6)
            
            # Parse and validate JSON
            slide_spec = self._parse_and_validate_response(raw_response)
            
            # Post-process
            slide_spec = self._post_process_slides(slide_spec, max_slides)
            
            print(f"✅ Đã tạo sườn nội dung cho {len(slide_spec.get('slides', []))} slides")
            return slide_spec

        except Exception as e:
            print(f"❌ Lỗi khi tạo slide content: {e}")
            return self._create_error_response(str(e), lesson_plan)

    def _format_objectives(self, objectives: List[str]) -> str:
        """Format objectives list"""
        if not objectives:
            return "Chưa có mục tiêu cụ thể"
        
        formatted = []
        for i, obj in enumerate(objectives[:6], 1):
            formatted.append(f"{i}. {obj}")
        return "\n".join(formatted)

    def _format_sections(self, sections: List[Dict[str, Any]]) -> str:
        """Format sections list"""
        if not sections:
            return "Chưa có nội dung chi tiết"
        
        formatted = []
        for i, section in enumerate(sections[:8], 1):
            heading = section.get("heading", f"Phần {i}")
            bullets = section.get("bullets", [])
            
            formatted.append(f"\n=== {heading} ===")
            if bullets:
                for bullet in bullets[:5]:
                    formatted.append(f"- {bullet}")
            else:
                formatted.append("- (Nội dung chưa chi tiết)")
        
        return "\n".join(formatted)

    def _parse_and_validate_response(self, raw_response: str) -> Dict[str, Any]:
        """Parse and validate JSON response from LLM"""
        try:
            # Remove code fence if present
            raw_response = self._strip_code_fence(raw_response)
            
            # Try to extract JSON
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                raw_response = json_match.group(0)
            
            # Parse JSON
            slide_spec = json.loads(raw_response)
            
            # Validate structure
            if not isinstance(slide_spec, dict):
                raise ValueError("Response is not a dictionary")
            
            if "slides" not in slide_spec:
                raise ValueError("No 'slides' key found")
            
            return slide_spec
            
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parsing error: {e}")
            raise ValueError(f"Invalid JSON response: {e}")
        except Exception as e:
            print(f"⚠️ Response validation error: {e}")
            raise ValueError(f"Response validation failed: {e}")

    def _strip_code_fence(self, text: str) -> str:
        """Remove ```json ... ``` wrapper if present"""
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(\w+)?\s*", "", text, flags=re.MULTILINE)
            text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
        return text.strip()

    def _post_process_slides(self, slide_spec: Dict[str, Any], max_slides: int) -> Dict[str, Any]:
        """Post-process and clean up slide specification"""
        # Ensure meta section
        if "meta" not in slide_spec:
            slide_spec["meta"] = {}
        
        meta = slide_spec["meta"]
        meta.setdefault("tone", "thân thiện")
        meta.setdefault("total_slides", len(slide_spec.get("slides", [])))
        
        # Process slides
        slides = slide_spec.get("slides", [])[:max_slides]
        
        for i, slide in enumerate(slides, 1):
            # Ensure required fields
            slide.setdefault("slide_number", i)
            slide.setdefault("type", "content")
            slide.setdefault("title", f"Slide {i}")
            slide.setdefault("subtitle", "")
            slide.setdefault("content", [])
            slide.setdefault("speaker_notes", "")
            slide.setdefault("image_suggestion", "")
            slide.setdefault("layout_type", "title_and_body")
            
            # Ensure content is list and truncate
            if isinstance(slide["content"], str):
                slide["content"] = [slide["content"]]
            elif not isinstance(slide["content"], list):
                slide["content"] = []
            
            # Limit bullet points and word count
            slide["content"] = slide["content"][:6]  # Max 6 bullets
            slide["content"] = [
                self._truncate_words(str(bullet), 12) 
                for bullet in slide["content"]
            ]
            
            # Truncate speaker notes
            slide["speaker_notes"] = self._truncate_words(
                str(slide.get("speaker_notes", "")), 50
            )
        
        slide_spec["slides"] = slides
        return slide_spec

    @staticmethod
    def _truncate_words(text: str, max_words: int) -> str:
        """Truncate text to max words"""
        words = str(text).split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]) + "..."

    def _create_error_response(self, error_msg: str, lesson_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Create error response structure"""
        return {
            "meta": {
                "title": lesson_plan.get("title", "Bài học"),
                "subject": lesson_plan.get("subject", ""),
                "grade": lesson_plan.get("grade", ""),
                "duration": lesson_plan.get("duration", ""),
                "total_slides": 0,
                "tone": "thân thiện",
                "status": "error",
                "error": error_msg
            },
            "slides": []
        }

    def format_slides_for_presentation(self, slide_spec: Dict[str, Any]) -> str:
        """
        Format slide specification thành text dễ đọc cho presentation
        """
        meta = slide_spec.get("meta", {})
        slides = slide_spec.get("slides", [])
        
        output = []
        
        # Header
        output.append("=" * 60)
        output.append(f"🎯 SƯỜN NỘI DUNG SLIDE: {meta.get('title', 'Bài học')}")
        output.append(f"📚 Môn: {meta.get('subject', '')} | Lớp: {meta.get('grade', '')}")
        output.append(f"⏰ Thời lượng: {meta.get('duration', '')} | Tổng slides: {len(slides)}")
        output.append("=" * 60)
        output.append("")
        
        # Slides content
        for slide in slides:
            slide_num = slide.get("slide_number", 0)
            slide_type = slide.get("type", "content").upper()
            title = slide.get("title", "")
            subtitle = slide.get("subtitle", "")
            content = slide.get("content", [])
            speaker_notes = slide.get("speaker_notes", "")
            image_suggestion = slide.get("image_suggestion", "")
            
            output.append(f"=== SLIDE {slide_num}: {title} [{slide_type}] ===")
            
            if subtitle:
                output.append(f"Phụ đề: {subtitle}")
                output.append("")
            
            # Content
            if content:
                for bullet in content:
                    output.append(f"{bullet}")
                output.append("")
            
            # Speaker notes
            if speaker_notes:
                output.append(f"📝 Ghi chú GV: {speaker_notes}")
                output.append("")
            
            # Image suggestion
            if image_suggestion:
                output.append(f"🖼️ Gợi ý hình ảnh: {image_suggestion}")
                output.append("")
            
            output.append("-" * 50)
            output.append("")
        
        return "\n".join(output)

    def export_to_simple_html(self, slide_spec: Dict[str, Any]) -> str:
        """
        Export slide content to simple HTML for viewing/printing
        """
        meta = slide_spec.get("meta", {})
        slides = slide_spec.get("slides", [])
        
        html = f"""
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{meta.get('title', 'Slides')}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; line-height: 1.6; }}
        .header {{ text-align: center; margin-bottom: 30px; border-bottom: 3px solid #007acc; padding-bottom: 20px; }}
        .slide {{ margin-bottom: 40px; border: 2px solid #ddd; border-radius: 10px; padding: 25px; page-break-inside: avoid; }}
        .slide-title {{ font-size: 1.8em; color: #007acc; margin-bottom: 15px; }}
        .slide-subtitle {{ font-size: 1.2em; color: #666; margin-bottom: 20px; }}
        .slide-content {{ margin-bottom: 20px; }}
        .slide-content li {{ margin-bottom: 8px; }}
        .speaker-notes {{ background: #f8f9fa; padding: 15px; border-left: 4px solid #28a745; margin-top: 15px; }}
        .image-suggestion {{ background: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; margin-top: 10px; }}
        @media print {{ .slide {{ page-break-after: always; }} }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{meta.get('title', 'Bài học')}</h1>
        <p><strong>Môn:</strong> {meta.get('subject', '')} | <strong>Lớp:</strong> {meta.get('grade', '')} | <strong>Thời lượng:</strong> {meta.get('duration', '')}</p>
        <p>Tổng số slides: {len(slides)}</p>
    </div>
"""
        
        for slide in slides:
            slide_num = slide.get("slide_number", 0)
            title = slide.get("title", "")
            subtitle = slide.get("subtitle", "")
            content = slide.get("content", [])
            speaker_notes = slide.get("speaker_notes", "")
            image_suggestion = slide.get("image_suggestion", "")
            
            html += f"""
    <div class="slide">
        <div class="slide-title">Slide {slide_num}: {title}</div>
        {f'<div class="slide-subtitle">{subtitle}</div>' if subtitle else ''}
        
        <div class="slide-content">
            <ul>
"""
            
            for bullet in content:
                html += f"                <li>{bullet}</li>\n"
            
            html += """            </ul>
        </div>
"""
            
            if speaker_notes:
                html += f"""        <div class="speaker-notes">
            <strong>📝 Ghi chú cho giáo viên:</strong> {speaker_notes}
        </div>
"""
            
            if image_suggestion:
                html += f"""        <div class="image-suggestion">
            <strong>🖼️ Gợi ý hình ảnh:</strong> {image_suggestion}
        </div>
"""
            
            html += "    </div>\n"
        
        html += """
</body>
</html>
"""
        return html


# Example usage
def example_usage():
    """
    Ví dụ sử dụng SlideContentWriterAgent
    """
    
    # Mock LLM client for testing
    class MockLLMClient:
        def chat(self, messages, temperature=0.6):
            return '''
{
  "meta": {
    "title": "Quang hợp ở thực vật",
    "subject": "Sinh học",
    "grade": "Lớp 10", 
    "duration": "45 phút",
    "total_slides": 8,
    "tone": "thân thiện"
  },
  "slides": [
    {
      "slide_number": 1,
      "type": "title",
      "title": "Quang hợp ở thực vật",
      "subtitle": "Sinh học lớp 10",
      "content": [
        "• Tìm hiểu bí mật của sự sống xanh",
        "• Khám phá cách thực vật tạo thức ăn"
      ],
      "speaker_notes": "Chào mừng các em đến với bài học về quang hợp. Hôm nay chúng ta sẽ tìm hiểu một trong những quá trình quan trọng nhất của sự sống.",
      "image_suggestion": "lá cây xanh, ánh nang mặt trời",
      "layout_type": "title_only"
    },
    {
      "slide_number": 2,
      "type": "content", 
      "title": "Mục tiêu bài học",
      "subtitle": "",
      "content": [
        "• Hiểu khái niệm quang hợp",
        "• Nắm được phương trình quang hợp",
        "• Biết điều kiện xảy ra quang hợp",
        "• Nhận biết vai trò của quang hợp"
      ],
      "speaker_notes": "Sau bài học này, các em sẽ hiểu được quang hợp là gì và tại sao nó lại quan trọng đối với sự sống.",
      "image_suggestion": "biểu đồ mục tiêu học tập",
      "layout_type": "title_and_body"
    },
    {
      "slide_number": 3,
      "type": "content",
      "title": "Quang hợp là gì?",
      "subtitle": "",
      "content": [
        "• Quá trình tạo thức ăn của thực vật",
        "• Sử dụng ánh sáng mặt trời",
        "• Chuyển CO₂ và H₂O thành glucose",
        "• Giải phóng O₂ ra môi trường"
      ],
      "speaker_notes": "Quang hợp chính là cách thực vật 'nấu ăn' bằng ánh sáng mặt trời. Chúng ta hãy xem chi tiết quá trình này.",
      "image_suggestion": "sơ đồ quang hợp, lục lạp",
      "layout_type": "title_and_body"
    }
  ]
}
'''
    
    # Test the agent
    mock_llm = MockLLMClient()
    agent = SlideContentWriterAgent(mock_llm)
    
    sample_lesson_plan = {
        "title": "Quang hợp ở thực vật",
        "subject": "Sinh học",
        "grade": "Lớp 10",
        "duration": "45 phút",
        "objectives": [
            "Hiểu khái niệm quang hợp",
            "Nắm được phương trình quang hợp",
            "Biết vai trò của quang hợp"
        ],
        "sections": [
            {
                "heading": "Khái niệm quang hợp",
                "bullets": ["Định nghĩa", "Điều kiện xảy ra", "Sản phẩm"]
            },
            {
                "heading": "Phương trình quang hợp",
                "bullets": ["Chất tham gia", "Sản phẩm", "Điều kiện"]
            }
        ]
    }
    
    # Generate slide content
    result = agent.run(sample_lesson_plan, max_slides=12)
    
    # Format for presentation
    formatted_text = agent.format_slides_for_presentation(result)
    print("FORMATTED TEXT OUTPUT:")
    print(formatted_text)
    
    # Export to HTML
    html_output = agent.export_to_simple_html(result)
    print("\nHTML OUTPUT GENERATED (first 500 chars):")
    print(html_output[:500] + "...")
    
    return result


if __name__ == "__main__":
    example_result = example_usage()
    print(f"\nExample completed with {len(example_result.get('slides', []))} slides generated.")
    
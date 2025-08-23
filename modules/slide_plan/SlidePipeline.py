import os
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from utils.GPTClient import GPTClient
from modules.agents.SlideOutlineAgent import SlideOutlineAgent

class SlidePipeline:
    """
    Pipeline tạo slide content từ lesson plan:
      1) Nhận lesson plan content
      2) Sử dụng SlideOutlineAgent để tạo slide outline
      3) Lưu kết quả dưới dạng markdown
    """
    def __init__(self, llm: GPTClient, credentials_path: Optional[str] = None):
        self.llm = llm
        # Kiểm tra và khởi tạo SlideOutlineAgent an toàn
        try:
            if llm is None:
                print("⚠️ Warning: LLM is None, slide content generation may fail")
                self.slide_agent = None
            else:
                self.slide_agent = SlideOutlineAgent(llm)
        except Exception as e:
            print(f"⚠️ Warning: Cannot initialize SlideOutlineAgent: {e}")
            self.slide_agent = None
            
        self.output_dir = Path("output_slides")
        self.output_dir.mkdir(exist_ok=True)

    def __call__(self, state: 'FlowState') -> Dict[str, Any]:
        """Phương thức __call__ để tích hợp với langgraph."""
        print("\n📊 Bắt đầu tạo Slide Plan...")
        form = state.get("form_data", {}) or {}
        content_types = form.get("content_types", [])

        if "slide_plan" not in content_types:
            print("⭐ Skip tạo Slide Plan (user không tick)")
            return {"slide_plan": {}, "__slide_done__": True}

        prompt = state.get("user_prompt", "")
        lesson_plan = state.get("lesson_plan", {})

        if not prompt and not lesson_plan:
            return {"slide_plan": {"error": "Không có prompt hoặc lesson plan để tạo slide"}, "__slide_done__": True}

        lesson_plan_content = (
            lesson_plan.get("complete_markdown", "")
            or lesson_plan.get("markdown", "")
            or json.dumps(lesson_plan, ensure_ascii=False)
        )

        slide_config = form.get("slide_config", {}) or {
            "tone": "thân thiện"
        }
        
        slide_plan = self.create_slide_from_lesson_plan(
            lesson_plan_content=lesson_plan_content,
            user_requirements=prompt,
            slide_config=slide_config
        )

        print("✅ Hoàn thành tạo Slide Plan!")
        if slide_plan.get("success") and "markdown_path" in slide_plan:
            print(f"📄 Đã lưu tại: {slide_plan['markdown_path']}")

        return {"slide_plan": slide_plan, "__slide_done__": True}

    def create_slide_from_lesson_plan(
        self,
        lesson_plan_content: str,
        user_requirements: str = "",
        slide_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Tạo slide content từ lesson plan → Markdown file
        slide_config:
            - tone: phong cách slide (thân thiện, chuyên nghiệp, ...)
        """
        try:
            print("🎬 Bắt đầu tạo slide content từ lesson plan...")
            cfg = slide_config or {}

            # 1) Validate input
            if not lesson_plan_content or (isinstance(lesson_plan_content, str) and lesson_plan_content.strip() == ""):
                print("❌ Lesson plan content is empty or None")
                return {"success": False, "error": "Lesson plan content is empty"}

            # 2) Parse lesson plan content safely
            lesson_plan = None
            try:
                if isinstance(lesson_plan_content, str):
                    # Kiểm tra nếu string rỗng hoặc chỉ có whitespace
                    content_stripped = lesson_plan_content.strip()
                    if not content_stripped:
                        raise ValueError("Empty lesson plan content")
                    
                    # Thử parse JSON trước
                    try:
                        lesson_plan = json.loads(content_stripped)
                    except json.JSONDecodeError:
                        # Nếu không phải JSON, coi như markdown content
                        lesson_plan = {
                            "complete_markdown": lesson_plan_content,
                            "mon_hoc": cfg.get("subject", "Chưa xác định"),
                            "grade_level": cfg.get("grade", "Chưa xác định"),
                            "title": cfg.get("title", "Bài học"),
                            "duration": cfg.get("duration", "45 phút")
                        }
                else:
                    lesson_plan = lesson_plan_content
            except (json.JSONDecodeError, ValueError) as e:
                print(f"⚠️ JSON parse error, treating as markdown: {e}")
                # Fallback: treat as markdown content
                lesson_plan = {
                    "complete_markdown": lesson_plan_content,
                    "mon_hoc": cfg.get("subject", "Chưa xác định"),
                    "grade_level": cfg.get("grade", "Chưa xác định"),
                    "title": cfg.get("title", "Bài học"),
                    "duration": cfg.get("duration", "45 phút")
                }
            except Exception as e:
                print(f"❌ Unexpected error parsing lesson plan: {e}")
                return {"success": False, "error": f"Error parsing lesson plan: {e}"}

            # 3) Generate slide content using SlideOutlineAgent
            try:
                print(f"🔍 Debug - lesson_plan keys: {list(lesson_plan.keys()) if isinstance(lesson_plan, dict) else 'Not dict'}")
                print(f"🔍 Debug - slide_agent: {self.slide_agent}")
                
                # Kiểm tra slide_agent có được khởi tạo đúng không
                if not self.slide_agent or not hasattr(self.slide_agent, 'run'):
                    print("❌ Slide agent not properly initialized, creating fallback slide content")
                    slide_content = self._create_fallback_slide_content(lesson_plan, cfg)
                else:
                    # Chuẩn bị lesson plan content cho SlideOutlineAgent
                    if isinstance(lesson_plan, dict):
                        lesson_content = (
                            lesson_plan.get("complete_markdown", "") or
                            lesson_plan.get("markdown", "") or
                            json.dumps(lesson_plan, ensure_ascii=False)
                        )
                    else:
                        lesson_content = str(lesson_plan)
                    
                    slide_content = self.slide_agent.run(
                        lesson_plan_content=lesson_content,
                        user_requirements=user_requirements
                    )
                
                print(f"✅ Generated slide content: {len(slide_content)} characters")
                
            except Exception as e:
                print(f"❌ Error generating slide content: {e}")
                traceback.print_exc()
                print("📄 Creating fallback slide content...")
                slide_content = self._create_fallback_slide_content(lesson_plan, cfg)

            # 4) Save slide content to markdown file
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Tạo filename từ topic hoặc title
                topic = ""
                if isinstance(lesson_plan, dict):
                    topic = lesson_plan.get("title", "") or lesson_plan.get("mon_hoc", "")
                topic_slug = self._slugify(topic) if topic else "slide"
                
                md_filename = f"{topic_slug}_{timestamp}.md"
                md_path = self.output_dir / md_filename
                
                md_path.write_text(slide_content, encoding="utf-8")
                print(f"✅ Slide content saved to: {md_path}")
                
            except Exception as e:
                print(f"❌ Error saving slide content: {e}")
                return {"success": False, "error": f"Error saving slide content: {e}"}

            # 5) Create metadata
            slide_count = self._count_slides(slide_content)
            result_data = {
                "success": True,
                "markdown_path": str(md_path),
                "slide_count": slide_count,
                "content_preview": slide_content[:500] + "..." if len(slide_content) > 500 else slide_content,
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "slide_count": slide_count,
                    "filename": md_filename,
                },
            }

            print(f"✅ Hoàn thành: {slide_count} slides → {md_path}")
            return result_data

        except Exception as e:
            msg = f"Lỗi trong pipeline tạo slide: {e}"
            print(f"❌ {msg}")
            traceback.print_exc()
            return {"success": False, "error": msg, "slide_count": 0}

    def _create_fallback_slide_content(self, lesson_plan: dict, cfg: dict) -> str:
        """Tạo slide content đơn giản khi SlideOutlineAgent không hoạt động"""
        print("📄 Creating fallback slide content...")
        
        # Lấy thông tin cơ bản
        subject = lesson_plan.get("mon_hoc", cfg.get("subject", "Bài học"))
        title = lesson_plan.get("title", f"Bài học: {subject}")
        grade = lesson_plan.get("grade_level", cfg.get("grade", ""))
        duration = lesson_plan.get("duration", "45 phút")
        
        # Tạo slide content cơ bản theo format của SlideOutlineAgent
        fallback_content = f"""=== SLIDE 1: {title.upper()} ===
🎯 **Bài học:** {title}
📚 **Môn học:** {subject}
📊 **Lớp:** {grade if grade else "Tất cả các lớp"}
⏰ **Thời gian:** {duration}
🚀 **Hôm nay chúng ta sẽ khám phá kiến thức mới!**

---

=== SLIDE 2: MỤC TIÊU BÀI HỌC ===
Sau bài học này, các em sẽ có thể:

✅ Hiểu được khái niệm cơ bản của bài học
✅ Áp dụng kiến thức vào thực tế
✅ Phân tích và đánh giá nội dung học tập
✅ Rút ra được kết luận quan trọng

---

=== SLIDE 3: KIẾN THỨC CŨ ===
🔄 **Ôn tập:**
• Các kiến thức đã học trước đó
• Mối liên hệ với bài học mới
• Những điều cần nhớ
• Chuẩn bị cho nội dung mới

Ghi chú: Dành 5-7 phút để ôn tập và kích hoạt kiến thức cũ
---

=== SLIDE 4: NỘI DUNG CHÍNH - PHẦN 1 ===
📖 **Khái niệm cơ bản:**
• Định nghĩa và đặc điểm
• Ví dụ minh họa cụ thể  
• Ứng dụng trong thực tế
• Những điều cần lưu ý

---

=== SLIDE 5: NỘI DUNG CHÍNH - PHẦN 2 ===
🔍 **Phân tích sâu hơn:**
• Các yếu tố quan trọng
• Mối quan hệ cause-effect
• So sánh và đối chiếu
• Ví dụ thực tế

---

=== SLIDE 6: THỰC HÀNH ===
🎯 **Hoạt động học tập:**
• Bài tập cá nhân (5 phút)
• Thảo luận nhóm (10 phút)
• Trình bày kết quả (5 phút)
• Nhận xét và đánh giá

Ghi chú: Khuyến khích học sinh tham gia tích cực
---

=== SLIDE 7: TÓM TẮT VÀ KẾT LUẬN ===
📋 **Những điều cần nhớ:**

✅ Khái niệm cơ bản đã học
✅ Ứng dụng thực tế quan trọng
✅ Kỹ năng đã rèn luyện
✅ Kiến thức nền tảng cho bài sau

---

=== SLIDE 8: BÀI TẬP VỀ NHÀ & Q&A ===
📝 **Bài tập về nhà:**
• Ôn tập nội dung đã học
• Làm bài tập SGK trang XX
• Chuẩn bị cho bài học tiếp theo

❓ **Có câu hỏi nào không?**
💬 **Thảo luận và trao đổi**

**Bài tiếp theo:** [Tên bài học tiếp theo]
---
"""
        
        print(f"✅ Created fallback slide content with {self._count_slides(fallback_content)} slides")
        return fallback_content

    def _count_slides(self, content: str) -> int:
        """Đếm số lượng slide trong content"""
        import re
        return len(re.findall(r'=== SLIDE \d+:', content))

    def _slugify(self, s: str) -> str:
        """Tạo slug từ string"""
        import unicodedata
        import re
        s = (s or "").strip().lower()
        s = unicodedata.normalize("NFD", s)
        s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
        s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
        return s[:50]  # Giới hạn độ dài

    def get_slide_summary(self, slide_content: str) -> Dict[str, Any]:
        """
        Tạo summary thông tin về slides đã tạo
        """
        import re
        slides = re.findall(r'=== SLIDE (\d+): (.*?) ===', slide_content)
        
        return {
            "total_slides": len(slides),
            "slide_titles": [{"number": int(num), "title": title.strip()} 
                           for num, title in slides],
            "estimated_duration": len(slides) * 3,  # ~3 phút/slide
            "content_length": len(slide_content)
        }

# Alias để giữ tương thích
GoogleSlidePipeline = SlidePipeline

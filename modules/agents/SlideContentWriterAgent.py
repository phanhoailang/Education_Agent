# SlideContentWriterAgent.py
from typing import Dict, Any, List, Optional
import json
import re
from utils.GPTClient import GPTClient
# from utils.GeminiClient import GeminiClient  # nếu muốn dùng Gemini

class SlideContentWriterAgent:
    """
    Nhận lesson_plan (hoặc slide_outline) và sinh SlideSpec để render bằng Google Slides.
    Tập trung vào: bullet <= 6 dòng/slide, mỗi bullet <= 12 từ (quy tắc 6x6), speaker notes rõ ràng,
    gợi ý ảnh (imageQuery) & layout hint để renderer chọn template phù hợp.
    """

    def __init__(self, llm: GPTClient):
        # def __init__(self, llm: GeminiClient):
        self.llm = llm
        self.system_prompt = """
Bạn là Instructional Designer & Presentation Expert.
Mục tiêu: CHUYỂN đổi kế hoạch bài giảng thành NỘI DUNG SLIDE cô đọng, dễ trình bày.

NGUYÊN TẮC SLIDE:
- Quy tắc 6x6: tối đa 6 bullet/slide, mỗi bullet ≲ 12 từ; tránh đoạn văn.
- Ngôn ngữ phù hợp lứa tuổi; dùng động từ hành động; tránh trùng lặp tiêu đề.
- Có "speaker_notes" để giáo viên nói mạch lạc (2–5 câu/slide).
- Gợi ý ảnh bằng "imageQuery" (danh từ khóa, tiếng Việt hoặc tiếng Anh, không URL).
- Đề xuất "layout_hint" trong: ["TITLE_ONLY","TITLE_AND_BODY","TITLE_AND_TWO_COLUMNS","TITLE_BODY_IMAGE_RIGHT","TITLE_BODY_IMAGE_LEFT"].

ĐỊNH DẠNG OUTPUT (JSON hợp lệ, KHÔNG markdown, KHÔNG giải thích ngoài JSON):
{
  "meta": {
    "title": "<tiêu đề bài>",
    "subject": "<môn>",
    "grade": "<lớp>",
    "duration": "<thời lượng>",
    "tone": "nghiêm túc|thân thiện|sôi động"
  },
  "slides": [
    {
      "type": "title",                      // title | agenda | content | activity | summary | quiz
      "title": "Tiêu đề",
      "subtitle": "Phụ đề (nếu có)",
      "bullets": [],
      "speaker_notes": "…",
      "imageQuery": null,
      "layout_hint": "TITLE_ONLY"
    },
    {
      "type": "content",
      "title": "Khái niệm chính",
      "bullets": ["…","…"],
      "speaker_notes": "…",
      "imageQuery": "chloroplast, photosynthesis diagram, leaf cross-section",
      "layout_hint": "TITLE_BODY_IMAGE_RIGHT"
    }
    // ...
  ]
}
Chỉ trả JSON theo schema trên.
        """.strip()

    def _strip_code_fence(self, text: str) -> str:
        """Loại bỏ ```json ... ``` nếu LLM bọc lại."""
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(\w+)?\s*", "", text, flags=re.MULTILINE)
            text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
        return text.strip()

    def _safe_json(self, text: str) -> Dict[str, Any]:
        text = self._strip_code_fence(text)
        # Thử tìm block JSON lớn nhất nếu có rác ngoài
        m = re.search(r"\{.*\}\s*$", text, flags=re.DOTALL)
        if m:
            text = m.group(0)
        return json.loads(text)

    def run(
        self,
        lesson_plan: Dict[str, Any],
        slide_outline: Optional[Dict[str, Any]] = None,
        *,
        subject: str = "",
        grade: str = "",
        style_tone: str = "thân thiện",
        max_slides: int = 18
    ) -> Dict[str, Any]:
        """
        - lesson_plan: JSON kế hoạch bài giảng hiện có (title, objectives, sections…)
        - slide_outline: (tuỳ chọn) khung slide do SlideOutlineAgent sinh.
        - subject/grade: ghi đè nếu lesson_plan thiếu.
        - max_slides: giới hạn để giữ deck gọn.
        Trả về: SlideSpec (dict) theo schema ở system prompt.
        """
        try:
            # Ráp context gọn gàng
            lp_title = lesson_plan.get("title", "")
            lp_obj = lesson_plan.get("objectives", [])
            lp_secs = lesson_plan.get("sections", [])

            user_prompt = f"""
DỮ LIỆU ĐẦU VÀO
=== LESSON PLAN ===
Title: {lp_title}
Subject: {subject or lesson_plan.get("mon_hoc","")}
Grade: {grade or lesson_plan.get("grade_level","")}
Duration: {lesson_plan.get("duration","")}
Objectives: {lp_obj}

Sections (rút gọn):
{[
  {"heading": s.get("heading",""), "bullets": (s.get("bullets") or [])[:6]}
  for s in lp_secs[:10]
]}

=== SLIDE OUTLINE (optional) ===
{slide_outline if slide_outline else "None"}

YÊU CẦU
- Tạo deck tối đa {max_slides} slide gồm: title, (tuỳ chọn) agenda, content/activity, summary.
- Mỗi slide: tuân thủ quy tắc 6x6, có speaker_notes, gợi ý imageQuery nếu phù hợp.
- Tone: {style_tone}.
- Trả về JSON đúng schema, KHÔNG kèm giải thích.
""".strip()

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            raw = self.llm.chat(messages, temperature=0.4)
            spec = self._safe_json(raw)

            # Hậu kiểm tối giản (giữ an toàn cho renderer)
            slides: List[Dict[str, Any]] = spec.get("slides", [])
            # Giới hạn số slide & số bullet
            slides = slides[:max_slides]
            for sl in slides:
                if isinstance(sl.get("bullets"), list):
                    sl["bullets"] = [self._truncate_words(b, 12) for b in sl["bullets"][:6]]
                # đảm bảo trường bắt buộc
                sl.setdefault("speaker_notes", "")
                sl.setdefault("layout_hint", "TITLE_AND_BODY")
                sl.setdefault("imageQuery", None)
                sl.setdefault("type", "content")
                sl.setdefault("title", "")
            spec["slides"] = slides

            # Điền meta nếu thiếu
            spec.setdefault("meta", {})
            spec["meta"].setdefault("title", lp_title or "Bài học")
            spec["meta"].setdefault("subject", subject or lesson_plan.get("mon_hoc",""))
            spec["meta"].setdefault("grade", grade or lesson_plan.get("grade_level",""))
            spec["meta"].setdefault("duration", lesson_plan.get("duration",""))
            spec["meta"].setdefault("tone", style_tone)

            return spec

        except Exception as e:
            raise RuntimeError(f"SlideContentWriterAgent error: {e}")

    @staticmethod
    def _truncate_words(text: str, max_words: int) -> str:
        words = str(text).split()
        return " ".join(words[:max_words]) + ("" if len(words) <= max_words else "…")

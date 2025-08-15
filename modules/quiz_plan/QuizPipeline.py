import os
import json
import datetime
import re
import logging
from typing import Dict, Any, List, Tuple, Optional, Callable, Iterable

from utils.GPTClient import GPTClient
from modules.agents.QuizOutlineAgent import QuizOutlineAgent
from modules.agents.QuizContentGeneratorAgent import QuizContentGeneratorAgent


class QuizPipeline:
    """Pipeline tạo bộ câu hỏi trắc nghiệm từ prompt + tài liệu (chunks).

    - Bước 1: Gọi QuizOutlineAgent để sinh outline (khung đề)
    - Bước 2: Gọi QuizContentGeneratorAgent sinh câu hỏi theo 4 mức độ
    - Bước 3: Hợp nhất và render Markdown + trích xuất đáp án
    - Bước 4: Lưu JSON, Markdown, Answer Key ra ổ đĩa

    Ngoài hàm `create_full_quiz`, có thêm `create_full_quiz_stream` để phục vụ UI streaming.
    """

    QUESTION_TYPES = ["NHẬN BIẾT", "THÔNG HIỂU", "VẬN DỤNG", "VẬN DỤNG CAO"]

    def __init__(
        self,
        llm: GPTClient,
        output_dir: str = "output_quizzes",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.outline_agent = QuizOutlineAgent(llm)
        self.content_agent = QuizContentGeneratorAgent(llm)
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self.logger = logger or logging.getLogger(__name__)
        if not self.logger.handlers:
            # Thiết lập logger mặc định nếu chưa có
            handler = logging.StreamHandler()
            formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    # =========================== PUBLIC APIs =========================== #
    def create_full_quiz(self, user_prompt: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Tạo bộ câu hỏi trắc nghiệm hoàn chỉnh (non-stream)."""
        self._validate_inputs(user_prompt, chunks)

        self.logger.info("📝 Bắt đầu tạo bộ câu hỏi trắc nghiệm...")
        self.logger.info("💬 Prompt: %s", user_prompt)
        self.logger.info("📚 Có %d chunks tài liệu", len(chunks))

        # 1) Tạo outline
        self.logger.info("📋 Bước 1: Tạo khung bộ câu hỏi...")
        outline_raw = self.outline_agent.run(user_prompt)
        outline = self._ensure_outline_text(outline_raw)

        if isinstance(outline, str) and "Lỗi khi tạo outline" in outline:
            return {"error": f"Lỗi tạo outline: {outline}"}

        self.logger.info("✅ Đã tạo xong outline")

        # 2) Trích thông tin metadata
        mon_hoc, lop_hoc, chu_de, so_cau, muc_do = self._extract_info_from_outline(outline)
        self.logger.info(
            "🔍 Đã trích xuất: Môn %s - Lớp %s - Chủ đề '%s' - %s câu - Mức độ %s",
            mon_hoc,
            lop_hoc,
            chu_de,
            so_cau,
            muc_do,
        )

        # 3) Sinh nội dung câu hỏi
        self.logger.info("📝 Bước 2: Tạo câu hỏi chi tiết...")
        quiz_content: Dict[str, str] = {}
        for qtype in self.QUESTION_TYPES:
            self.logger.info("   ✍️ Đang tạo câu hỏi: %s", qtype)
            questions = self.content_agent.run(qtype, outline, chunks, mon_hoc, lop_hoc, chu_de, so_cau)
            if isinstance(questions, dict):
                # Nếu agent trả về dict, cố gắng chuyển thành chuỗi
                questions = questions.get("content") or questions.get("markdown") or json.dumps(questions, ensure_ascii=False, indent=2)
            questions = (questions or "").strip()

            if questions:
                quiz_content[qtype] = questions
                self.logger.info("   ✅ Hoàn thành câu hỏi %s", qtype)
                preview = questions[:200] + ("..." if len(questions) > 200 else "")
                self.logger.debug("   📝 Preview: %s", preview)
            else:
                self.logger.warning("   ⚠️ Không có câu hỏi %s", qtype)

        # 4) Render Markdown
        self.logger.info("📄 Bước 3: Tạo file markdown hoàn chỉnh...")
        merged_markdown = self._create_complete_markdown(outline, quiz_content, mon_hoc, lop_hoc, chu_de)

        # 5) Tạo đáp án
        self.logger.info("🔑 Bước 4: Tạo đáp án...")
        answer_key = self._extract_answer_key(quiz_content)

        # 6) Gộp kết quả + metadata
        result = self._make_result(
            outline=outline,
            quiz_content=quiz_content,
            merged_markdown=merged_markdown,
            answer_key=answer_key,
            user_prompt=user_prompt,
            chunks_used=len(chunks),
            mon_hoc=mon_hoc,
            lop_hoc=lop_hoc,
            chu_de=chu_de,
            so_cau=so_cau,
            muc_do=muc_do,
        )

        # 7) Lưu file
        json_path = self._save_quiz(result)
        md_path = self._save_markdown_quiz(merged_markdown, mon_hoc, lop_hoc, chu_de)
        answer_path = self._save_answer_key(answer_key, mon_hoc, lop_hoc, chu_de)

        result["output_path"] = json_path
        result["markdown_path"] = md_path
        result["answer_key_path"] = answer_path

        self.logger.info("🎉 HOÀN THÀNH!")
        self.logger.info("📊 Tổng kết:")
        self.logger.info("   - Outline: %d ký tự", len(outline))
        self.logger.info("   - Câu hỏi: %d loại", len(self.QUESTION_TYPES))
        self.logger.info("   - Tổng câu: %d câu", result["metadata"]["total_questions"])
        self.logger.info("   - Sử dụng: %d chunks", len(chunks))
        self.logger.info("   - File JSON: %s", json_path)
        self.logger.info("   - File Markdown: %s", md_path)
        self.logger.info("   - File đáp án: %s", answer_path)

        return result

    def create_full_quiz_stream(
        self,
        user_prompt: str,
        chunks: List[Dict[str, Any]],
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Iterable[Dict[str, Any]]:
        """Tạo quiz theo dạng streaming: yield các sự kiện theo tiến độ.

        `on_event` (nếu truyền) sẽ được gọi với payload giống như yield.
        """
        self._validate_inputs(user_prompt, chunks)

        def emit(event: Dict[str, Any]):
            if on_event:
                try:
                    on_event(event)
                except Exception as _:
                    pass
            return event

        yield emit({"type": "start", "message": "Bắt đầu tạo bộ câu hỏi", "prompt": user_prompt, "chunks": len(chunks)})

        outline_raw = self.outline_agent.run(user_prompt)
        outline = self._ensure_outline_text(outline_raw)
        if isinstance(outline, str) and "Lỗi khi tạo outline" in outline:
            yield emit({"type": "error", "stage": "outline", "message": outline})
            return
        yield emit({"type": "outline", "content": outline})

        mon_hoc, lop_hoc, chu_de, so_cau, muc_do = self._extract_info_from_outline(outline)
        yield emit({
            "type": "metadata",
            "mon_hoc": mon_hoc,
            "lop": lop_hoc,
            "chu_de": chu_de,
            "so_cau": so_cau,
            "muc_do": muc_do,
        })

        quiz_content: Dict[str, str] = {}
        for qtype in self.QUESTION_TYPES:
            questions = self.content_agent.run(qtype, outline, chunks, mon_hoc, lop_hoc, chu_de, so_cau)
            if isinstance(questions, dict):
                questions = questions.get("content") or questions.get("markdown") or json.dumps(questions, ensure_ascii=False, indent=2)
            questions = (questions or "").strip()

            quiz_content[qtype] = questions
            yield emit({"type": "section_done", "qtype": qtype, "content": questions})

        merged_markdown = self._create_complete_markdown(outline, quiz_content, mon_hoc, lop_hoc, chu_de)
        yield emit({"type": "merged_markdown", "content": merged_markdown})

        answer_key = self._extract_answer_key(quiz_content)
        yield emit({"type": "answer_key", "content": answer_key})

        result = self._make_result(
            outline=outline,
            quiz_content=quiz_content,
            merged_markdown=merged_markdown,
            answer_key=answer_key,
            user_prompt=user_prompt,
            chunks_used=len(chunks),
            mon_hoc=mon_hoc,
            lop_hoc=lop_hoc,
            chu_de=chu_de,
            so_cau=so_cau,
            muc_do=muc_do,
        )

        json_path = self._save_quiz(result)
        md_path = self._save_markdown_quiz(merged_markdown, mon_hoc, lop_hoc, chu_de)
        answer_path = self._save_answer_key(answer_key, mon_hoc, lop_hoc, chu_de)

        result.update({
            "output_path": json_path,
            "markdown_path": md_path,
            "answer_key_path": answer_path,
        })

        yield emit({"type": "done", "result": result})

    # =========================== HELPERS =========================== #
    def _validate_inputs(self, user_prompt: str, chunks: List[Dict[str, Any]]) -> None:
        if not isinstance(user_prompt, str) or not user_prompt.strip():
            raise ValueError("user_prompt phải là chuỗi không rỗng")
        if not isinstance(chunks, list):
            raise ValueError("chunks phải là list[dict]")
        for i, c in enumerate(chunks):
            if not isinstance(c, dict):
                raise ValueError(f"chunk tại index {i} không phải dict")

    def _ensure_outline_text(self, outline_raw: Any) -> str:
        """Chuẩn hóa kết quả outline về chuỗi."""
        if isinstance(outline_raw, str):
            return outline_raw
        if isinstance(outline_raw, dict):
            return outline_raw.get("outline") or outline_raw.get("content") or json.dumps(outline_raw, ensure_ascii=False, indent=2)
        return str(outline_raw)

    def _make_result(
        self,
        *,
        outline: str,
        quiz_content: Dict[str, str],
        merged_markdown: str,
        answer_key: Dict[str, Any],
        user_prompt: str,
        chunks_used: int,
        mon_hoc: str,
        lop_hoc: str,
        chu_de: str,
        so_cau: str,
        muc_do: str,
    ) -> Dict[str, Any]:
        return {
            "outline": outline,
            "quiz_content": quiz_content,
            "complete_markdown": merged_markdown,
            "answer_key": answer_key,
            "metadata": {
                "created_at": datetime.datetime.now().isoformat(),
                "chunks_used": chunks_used,
                "original_prompt": user_prompt,
                "mon_hoc": mon_hoc,
                "lop": lop_hoc,
                "chu_de": chu_de,
                "so_cau": so_cau,
                "muc_do": muc_do,
                "total_questions": self._count_questions(quiz_content),
            },
        }

    # -------- Outline parsing & metadata -------- #
    def _extract_info_from_outline(self, outline: str) -> Tuple[str, str, str, str, str]:
        """Trích xuất (môn học, lớp, chủ đề, số câu, mức độ) từ outline.
        Cố gắng bắt nhiều format: **Môn học:**, Môn học:, Subject:, ...
        """
        mon_hoc = self._search_first(
            outline,
            [r"\*\*Môn học:\*\*\s*(.+)", r"Môn học:\s*(.+)", r"Subject:\s*(.+)"],
        )
        lop = self._search_first(
            outline,
            [r"\*\*Lớp:\*\*\s*(.+)", r"Lớp:\s*(.+)", r"Grade:\s*(.+)"],
        )
        chu_de = self._search_first(
            outline,
            [r"\*\*Chủ đề:\*\*\s*(.+)", r"Chủ đề:\s*(.+)", r"Topic:\s*(.+)"],
        )
        so_cau = self._search_first(
            outline,
            [r"\*\*Số câu:\*\*\s*(\d+)", r"Số câu:\s*(\d+)", r"Number of Questions:\s*(\d+)"],
            default="20",
        )
        muc_do = self._search_first(
            outline,
            [r"\*\*Mức độ:\*\*\s*(.+)", r"Mức độ:\s*(.+)", r"Difficulty:\s*(.+)"],
            default="Hỗn hợp",
        )

        return mon_hoc or "", lop or "", chu_de or "", so_cau or "20", muc_do or "Hỗn hợp"

    def _search_first(self, text: str, patterns: List[str], default: Optional[str] = None) -> Optional[str]:
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(1).strip()
        return default

    # -------- Saving helpers -------- #
    def _safe_filename(self, name: str, fallback: str = "quiz") -> str:
        base = name or fallback
        base = "".join(c for c in base if c.isalnum() or c in (" ", "-", "_"))
        base = base.strip().replace(" ", "_")
        return base[:50] if base else fallback

    def _save_quiz(self, quiz: Dict[str, Any]) -> str:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        chu_de = quiz.get("metadata", {}).get("chu_de", "quiz")
        safe = self._safe_filename(chu_de)
        path = os.path.join(self.output_dir, f"quiz_{safe}_{timestamp}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(quiz, f, ensure_ascii=False, indent=2)
        return path

    def _save_markdown_quiz(self, markdown_content: str, mon_hoc: str, lop: str, chu_de: str) -> str:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = self._safe_filename(chu_de)
        path = os.path.join(self.output_dir, f"quiz_{safe}_{timestamp}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        return path

    def _save_answer_key(self, answer_key: Dict[str, Any], mon_hoc: str, lop: str, chu_de: str) -> str:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = self._safe_filename(chu_de)
        path = os.path.join(self.output_dir, f"answer_key_{safe}_{timestamp}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(answer_key, f, ensure_ascii=False, indent=2)
        return path

    # -------- Markdown rendering -------- #
    def _create_complete_markdown(
        self,
        outline: str,
        quiz_content: Dict[str, str],
        mon_hoc: str,
        lop: str,
        chu_de: str,
    ) -> str:
        outline_sections = self._parse_outline_sections(outline)
        md: List[str] = []

        # Header
        title = f"BỘ CÂU HỎI TRẮC NGHIỆM: {chu_de.upper() if chu_de else 'CHỦ ĐỀ'}"
        md.append(f"# {title}")
        md.append("")

        # Thông tin chung
        section_order = ["THÔNG TIN CHUNG", "YÊU CẦU BỘ ĐỀ", "PHÂN BỐ CÂU HỎI"]
        for section_name in section_order:
            if section_name in outline_sections:
                md.append(f"## {section_name}")
                md.append("")
                content = self._format_section_content(outline_sections[section_name])
                md.append(content)
                md.append("")

        # Câu hỏi
        md.append("## CÂU HỎI TRẮC NGHIỆM")
        md.append("")
        md.append("*Hướng dẫn: Chọn đáp án đúng nhất cho mỗi câu hỏi. Mỗi câu chỉ có 1 đáp án đúng.*")
        md.append("")
        md.append("---")
        md.append("")

        question_counter = 1
        for qtype in self.QUESTION_TYPES:
            content = quiz_content.get(qtype, "").strip()
            if not content:
                continue

            # Làm sạch tiêu đề lặp
            content = self._clean_duplicate_headers(content, qtype)

            # Đánh số lại câu hỏi liên tục
            content = self._renumber_questions(content, question_counter)
            cnt = self._count_questions_in_content(content)
            question_counter += cnt

            md.append(f"### {qtype}")
            md.append("")
            md.append(content)
            md.append("")

        # Footer
        timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        md.append("---")
        md.append("")
        md.append(f"*Bộ câu hỏi được tạo tự động bởi EduMate AI - {timestamp}*")

        return "\n".join(md)

    def _clean_duplicate_headers(self, content: str, question_type: str) -> str:
        # Bỏ các header lặp/tạp
        patterns = [
            rf"^###\s*{re.escape(question_type)}\s*$",
            rf"^####?\s*\*\*?{re.escape(question_type)}\*\*?\s*$",
            rf"^###?\s*PHẦN\s*[\"']*{re.escape(question_type)}[\"']*\s*$",
            r"^---+\s*$",
        ]
        for p in patterns:
            content = re.sub(p, "", content, flags=re.IGNORECASE | re.MULTILINE)

        # Bỏ các phần phân tích không cần thiết (nếu có)
        content = re.sub(r"####?\s*\*\*?PHÂN TÍCH YÊU CẦU\*\*?.*?(?=####|\n\n|\Z)", "", content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r"####?\s*\*\*?CẤU TRÚC CÂU HỎI\*\*?", "", content, flags=re.IGNORECASE)
        return content.strip()

    def _renumber_questions(self, content: str, start_num: int) -> str:
        lines = content.split("\n")
        current = start_num
        out: List[str] = []

        patt = re.compile(r"^(\*\*)?Câu\s+(\d+)([:.])?(\*\*)?\s*", flags=re.IGNORECASE)
        for line in lines:
            m = patt.match(line.strip())
            if m:
                # Bảo toàn đậm nếu có
                bold_open = "**" if m.group(1) else ""
                bold_close = "**" if m.group(4) else ""
                rest = line.strip()[len(m.group(0)) :]
                out.append(f"{bold_open}Câu {current}:{bold_close} {rest}".rstrip())
                current += 1
            else:
                out.append(line)
        return "\n".join(out)

    def _count_questions_in_content(self, content: str) -> int:
        return len(re.findall(r"(?:\*\*)?Câu\s+\d+(?:[:.])", content))

    def _format_section_content(self, content: str) -> str:
        lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
        formatted: List[str] = []
        for ln in lines:
            if ln.startswith("**") and ln.rstrip().endswith(":**"):
                if formatted:
                    formatted.append("")
                formatted.append(ln)
            else:
                formatted.append(ln)
        return "\n".join(formatted)

    def _parse_outline_sections(self, outline: str) -> Dict[str, str]:
        sections: Dict[str, str] = {}
        lines = outline.split("\n")
        current_name: Optional[str] = None
        buffer: List[str] = []

        def flush():
            nonlocal current_name, buffer
            if current_name and buffer:
                sections[current_name] = "\n".join(buffer).strip()
            current_name, buffer = None, []

        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            # Nhận diện header dạng: #### I. TÊN, hoặc ### TÊN
            if line.startswith("####") and any(tok in line for tok in ["I.", "II.", "III.", "IV.", "V.", "VI.", "VII.", "VIII."]):
                flush()
                name = line.replace("####", "").strip()
                if "." in name:
                    name = name.split(".", 1)[1].strip()
                current_name = name.upper()
            elif line.startswith("### "):
                flush()
                current_name = line.replace("###", "").strip().upper()
            else:
                if current_name:
                    buffer.append(line)
        flush()
        return sections

    # -------- Answer key extraction -------- #
    def _extract_answer_key(self, quiz_content: Dict[str, str]) -> Dict[str, Any]:
        """Trích xuất đáp án từ nội dung câu hỏi.
        Hỗ trợ các format:
        - Dòng riêng: "Đáp án: C" / "Answer: B"
        - Đánh dấu (✓) / in đậm phương án đúng: "C. **...**" (hạn chế)
        """
        answers: Dict[str, str] = {}
        explanations: Dict[str, str] = {}
        stats_by_type: Dict[str, int] = {}

        q_index = 1
        for qtype, content in quiz_content.items():
            count_this_type = 0
            lines = [ln.rstrip() for ln in content.split("\n")]

            current_q = None
            current_exp: List[str] = []
            current_ans: Optional[str] = None

            for ln in lines:
                ln_strip = ln.strip()

                # Bắt đầu câu hỏi mới
                if re.match(r"^(?:\*\*)?Câu\s+\d+(?:[:.])", ln_strip, flags=re.IGNORECASE):
                    if current_q is not None:
                        if current_ans:
                            answers[str(q_index)] = current_ans
                        if current_exp:
                            explanations[str(q_index)] = "\n".join(current_exp).strip()
                        q_index += 1
                        count_this_type += 1
                        current_exp = []
                        current_ans = None
                    current_q = q_index
                    continue

                # Đáp án trực tiếp
                m1 = re.search(r"(?:Đáp án|Answer)\s*[:：]\s*([A-D])", ln_strip, flags=re.IGNORECASE)
                if m1:
                    current_ans = m1.group(1).upper()
                    continue

                # Dòng lựa chọn có đánh dấu ✓ hoặc (Correct)
                if re.match(r"^[A-D][).]\s*", ln_strip):
                    if "✓" in ln_strip or "(Correct)" in ln_strip or "[Correct]" in ln_strip:
                        current_ans = ln_strip[0].upper()
                        continue
                    # Heuristic: nếu phương án được bôi đậm toàn nội dung
                    if "**" in ln_strip and ln_strip.startswith(("A", "B", "C", "D")):
                        current_ans = ln_strip[0].upper()
                        continue

                # Giải thích
                if ln_strip.lower().startswith(("*giải thích", "giải thích", "*explanation", "explanation")):
                    current_exp.append(ln_strip)
                    continue
                if current_exp and (not re.match(r"^[A-D][).]", ln_strip)):
                    current_exp.append(ln_strip)

            # Flush câu cuối cùng của loại này
            if current_q is not None:
                if current_ans:
                    answers[str(q_index)] = current_ans
                if current_exp:
                    explanations[str(q_index)] = "\n".join(current_exp).strip()
                count_this_type += 1
                q_index += 1

            stats_by_type[qtype] = max(count_this_type, 0)

        total_questions = max(q_index - 1, 0)
        return {
            "answers": answers,
            "explanation": explanations,
            "statistics": {
                "total_questions": total_questions,
                "by_type": stats_by_type,
            },
        }

    def _count_questions(self, quiz_content: Dict[str, str]) -> int:
        total = 0
        for content in quiz_content.values():
            total += len(re.findall(r"(?:\*\*)?Câu\s+\d+(?:[:.])", content))
        return total
        
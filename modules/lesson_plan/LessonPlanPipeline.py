import os
import json
import datetime
import re
from typing import Dict, Any, List
from utils.GPTClient import GPTClient
from modules.agents.LessonPlanOutlineAgent import LessonPlanOutlineAgent
from modules.agents.LessonContentWriterAgent import LessonContentWriterAgent

class LessonPlanPipeline:
    def __init__(self, llm: GPTClient):
        self.outline_agent = LessonPlanOutlineAgent(llm)
        self.content_agent = LessonContentWriterAgent(llm)
        
    def create_full_lesson_plan(self, user_prompt: str, chunks: List[Dict]) -> Dict[str, Any]:
        """
        Tạo kế hoạch bài giảng hoàn chỉnh từ prompt và chunks
        """
        print(f"\n🎓 Bắt đầu tạo kế hoạch bài giảng...")
        print(f"📝 Prompt: {user_prompt}")
        print(f"📚 Có {len(chunks)} chunks tài liệu")
        
        # Bước 1: Tạo outline
        print("\n📋 Bước 1: Tạo khung kế hoạch bài giảng...")
        outline = self.outline_agent.run(user_prompt)
        
        if "Lỗi khi tạo outline" in outline:
            return {"error": f"Lỗi tạo outline: {outline}"}
        
        print("✅ Đã tạo xong outline")
        
        # Trích xuất thông tin từ outline
        mon_hoc, lop, ten_bai = self._extract_info_from_outline(outline)
        print(f"\n🔍 Đã trích xuất: Môn {mon_hoc} - Lớp {lop} - Bài '{ten_bai}'")
        
        # Bước 2: Viết nội dung chi tiết cho từng phần
        print("\n📝 Bước 2: Viết nội dung chi tiết...")
        
        sections_to_write = [
            "KHỞI ĐỘNG",
            "HÌNH THÀNH KIẾN THỨC", 
            "LUYỆN TẬP",
            "VẬN DỤNG/MỞ RỘNG"
        ]
        
        detailed_content = {}
        
        for section in sections_to_write:
            print(f"\n   ✍️ Đang viết phần: {section}")
            content = self.content_agent.run(section, outline, chunks, mon_hoc, lop, ten_bai)
            detailed_content[section] = content
            print(f"   ✅ Hoàn thành phần {section}")
            # In preview của content
            preview = content[:200] + "..." if len(content) > 200 else content
            print(f"   📝 Preview: {preview}")
        
        # Bước 3: Merge thành markdown hoàn chỉnh
        print("\n📄 Bước 3: Tạo file markdown hoàn chỉnh...")
        merged_markdown = self._create_complete_markdown(outline, detailed_content, mon_hoc, lop, ten_bai)
        
        # Bước 4: Kết hợp tất cả dữ liệu
        full_lesson_plan = {
            "outline": outline,
            "detailed_content": detailed_content,
            "complete_markdown": merged_markdown,
            "metadata": {
                "created_at": datetime.datetime.now().isoformat(),
                "chunks_used": len(chunks),
                "original_prompt": user_prompt,
                "mon_hoc": mon_hoc,
                "lop": lop,
                "ten_bai": ten_bai
            }
        }
        
        # Bước 5: Lưu cả JSON và Markdown
        json_path = self._save_lesson_plan(full_lesson_plan)
        md_path = self._save_markdown_plan(merged_markdown, mon_hoc, lop, ten_bai)
        
        full_lesson_plan["output_path"] = json_path
        full_lesson_plan["markdown_path"] = md_path
        
        print(f"\n🎉 HOÀN THÀNH!")
        print(f"📊 Tổng kết:")
        print(f"   - Outline: {len(outline)} ký tự")
        print(f"   - Chi tiết: {len(sections_to_write)} phần")
        print(f"   - Sử dụng: {len(chunks)} chunks")
        print(f"   - File JSON: {json_path}")
        print(f"   - File Markdown: {md_path}")
        
        return full_lesson_plan
    
    def _extract_info_from_outline(self, outline: str) -> tuple:
        """
        Trích xuất thông tin môn học, lớp, tên bài từ outline
        """
        mon_hoc = ""
        lop = ""
        ten_bai = ""
        
        # Tìm môn học
        mon_match = re.search(r'\*\*Môn học:\*\*\s*(.+)', outline)
        if mon_match:
            mon_hoc = mon_match.group(1).strip()
        
        # Tìm lớp
        lop_match = re.search(r'\*\*Lớp:\*\*\s*(.+)', outline)
        if lop_match:
            lop = lop_match.group(1).strip()
            
        # Tìm tên bài
        bai_match = re.search(r'\*\*Bài học:\*\*\s*(.+)', outline)
        if bai_match:
            ten_bai = bai_match.group(1).strip()
        
        return mon_hoc, lop, ten_bai
    
    def _save_lesson_plan(self, lesson_plan: Dict[str, Any]) -> str:
        """
        Lưu kế hoạch bài giảng ra file JSON
        """
        os.makedirs("output_lesson_plans", exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Lấy tên bài học làm tên file
        ten_bai = lesson_plan.get("metadata", {}).get("ten_bai", "bai_hoc")
        safe_name = "".join(c for c in ten_bai if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')[:50]  # Giới hạn độ dài
        
        filename = f"lesson_plan_{safe_name}_{timestamp}.json"
        output_path = os.path.join("output_lesson_plans", filename)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(lesson_plan, f, ensure_ascii=False, indent=2)
        
        return output_path
    
    def _save_markdown_plan(self, markdown_content: str, mon_hoc: str, lop: str, ten_bai: str) -> str:
        """
        Lưu kế hoạch bài giảng ra file Markdown
        """
        os.makedirs("output_lesson_plans", exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Tạo tên file markdown
        safe_name = "".join(c for c in ten_bai if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')[:50]
        
        filename = f"lesson_plan_{safe_name}_{timestamp}.md"
        output_path = os.path.join("output_lesson_plans", filename)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
        return output_path
    
    def _create_complete_markdown(self, outline: str, detailed_content: Dict, mon_hoc: str, lop: str, ten_bai: str) -> str:
        """
        Tạo file markdown hoàn chỉnh từ outline và detailed content
        """
        # Parse outline để lấy các phần
        outline_sections = self._parse_outline_sections(outline)
        
        # Tạo markdown hoàn chỉnh
        md_content = []
        
        # Header
        md_content.append(f"# KẾ HOẠCH BÀI GIẢNG: {ten_bai.upper()}")
        md_content.append("")
        
        # Thêm outline sections (Thông tin chung, Mục tiêu, Chuẩn bị, etc.)
        section_order = ["THÔNG TIN CHUNG", "MỤC TIÊU BÀI HỌC", "CHUẨN BỊ"]
        
        for section_name in section_order:
            if section_name in outline_sections:
                md_content.append(f"## {section_name}")
                md_content.append("")
                
                # Format content với xuống dòng
                content = outline_sections[section_name]
                content = self._format_section_content(content)
                md_content.append(content)
                md_content.append("")
        
        # ✅ BỎ IV - Chỉ viết "TIẾN TRÌNH DẠY HỌC"
        md_content.append("## TIẾN TRÌNH DẠY HỌC")
        md_content.append("")
        
        # Mapping sections
        section_mapping = {
            "KHỞI ĐỘNG": "A. KHỞI ĐỘNG",
            "HÌNH THÀNH KIẾN THỨC": "B. HÌNH THÀNH KIẾN THỨC", 
            "LUYỆN TẬP": "C. LUYỆN TẬP",
            "VẬN DỤNG/MỞ RỘNG": "D. VẬN DỤNG/MỞ RỘNG"
        }
        
        for section_key, section_title in section_mapping.items():
            md_content.append(f"### {section_title}")
            md_content.append("")
            
            # ✅ THÊM nội dung chi tiết với cleaning toàn diện
            if section_key in detailed_content:
                content = detailed_content[section_key]
                
                # Clean tất cả header lặp lại
                content = self._clean_duplicate_headers(content, section_key, section_title)
                
                md_content.append(content)
                md_content.append("")
        
        # ✅ CHỈ THÊM ĐÁNH GIÁ - BỎ GỢI Ý
        if "ĐÁNH GIÁ" in outline_sections:
            md_content.append("## ĐÁNH GIÁ")
            md_content.append("")
            content = self._format_section_content(outline_sections["ĐÁNH GIÁ"])
            md_content.append(content)
            md_content.append("")
        
        # Footer
        timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        md_content.append("*Kế hoạch bài giảng được tạo tự động bởi EduMate AI - " + timestamp + "*")
        
        return "\n".join(md_content)

    def _clean_duplicate_headers(self, content: str, section_key: str, section_title: str) -> str:
        """
        Clean tất cả loại header lặp lại và content không cần thiết
        """
        # ✅ Bỏ tất cả header lặp
        content = re.sub(r'###\s*' + re.escape(section_key), '', content, flags=re.IGNORECASE)
        content = re.sub(r'###\s*' + re.escape(section_title), '', content, flags=re.IGNORECASE)
        content = re.sub(r'####?\s*\*\*?' + re.escape(section_key) + r'\*\*?', '', content, flags=re.IGNORECASE)
        content = re.sub(r'###?\s*PHẦN\s*["\'"]*' + re.escape(section_key) + r'["\'"]*', '', content, flags=re.IGNORECASE)
        
        # ✅ Bỏ "PHÂN TÍCH CONTEXT" và "CẤU TRÚC NỘI DUNG"
        content = re.sub(r'####?\s*\*\*?1\.\s*PHÂN TÍCH CONTEXT\*\*?.*?(?=####|\n\n|\Z)', '', content, flags=re.DOTALL|re.IGNORECASE)
        content = re.sub(r'####?\s*\*\*?2\.\s*CẤU TRÚC NỘI DUNG\*\*?', '', content, flags=re.IGNORECASE)
        content = re.sub(r'####?\s*\*\*?PHÂN TÍCH CONTEXT\*\*?.*?(?=####|\n\n|\Z)', '', content, flags=re.DOTALL|re.IGNORECASE)
        content = re.sub(r'####?\s*\*\*?CẤU TRÚC NỘI DUNG\*\*?', '', content, flags=re.IGNORECASE)
        
        # ✅ Bỏ tất cả dấu ---
        content = re.sub(r'^---+\s*$', '', content, flags=re.MULTILINE)
        
        # ✅ Bỏ content phân tích context
        lines = content.split('\n')
        cleaned_lines = []
        skip_context = False
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Bỏ qua phần phân tích context
            if any(phrase in line_lower for phrase in ['vị trí của phần này', 'mục tiêu cụ thể cần đạt', 'đặc điểm tâm lý lứa tuổi']):
                skip_context = True
                continue
            
            # Kết thúc skip khi gặp header mới hoặc nội dung thực
            if skip_context and (line.startswith('**') or line.startswith('####') or 'hoạt động' in line_lower):
                skip_context = False
            
            if not skip_context and line.strip():
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()

    def _format_section_content(self, content: str) -> str:
        """
        Format nội dung section với xuống dòng phù hợp
        """
        lines = content.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Thêm xuống dòng sau các mục lớn
            if line.startswith('**') and line.endswith(':**'):
                if formatted_lines:  # Không thêm dòng trống ở đầu
                    formatted_lines.append("")
                formatted_lines.append(line)
            else:
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    def _parse_outline_sections(self, outline: str) -> Dict[str, str]:
        """
        Parse outline thành các sections
        """
        sections = {}
        lines = outline.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Detect section headers (#### I., #### II., etc.)
            if line.startswith('####') and any(roman in line for roman in ['I.', 'II.', 'III.', 'IV.', 'V.', 'VI.']):
                # Save previous section
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # Start new section
                current_section = line.replace('####', '').strip()
                if '.' in current_section:
                    current_section = current_section.split('.', 1)[1].strip()
                current_content = []
            else:
                if current_section:
                    current_content.append(line)
        
        # Save last section
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections
    
    def _extract_section_outline(self, tien_trinh_content: str, section_key: str) -> str:
        """
        Trích xuất thông tin outline cho một section cụ thể
        """
        lines = tien_trinh_content.split('\n')
        in_section = False
        section_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if this is our section
            if section_key.upper() in line.upper() and ('**' in line or '#' in line):
                in_section = True
                continue
            
            # Check if we've moved to next section
            if in_section and ('**' in line or '#' in line) and any(other_section in line.upper() for other_section in ['KHỞI ĐỘNG', 'HÌNH THÀNH', 'LUYỆN TẬP', 'VẬN DỤNG'] if other_section not in section_key.upper()):
                break
                
            if in_section:
                section_lines.append(line)
        
        return '\n'.join(section_lines).strip()
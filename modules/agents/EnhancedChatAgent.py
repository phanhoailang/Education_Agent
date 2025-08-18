# modules/agents/EnhancedChatAgent.py
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import json

class InteractiveSession:
    def __init__(self, session_id: str, content: str, content_type: str):
        self.session_id = session_id
        self.content = content
        self.content_type = content_type  # "lesson_plan" or "quiz"
        self.created_at = datetime.now()
        self.last_modified = datetime.now()
        self.timer_thread = None
        self.is_active = True
        self.refinement_count = 0
        self.refinement_history = []
        
    def reset_timer(self):
        """Reset timer về 5 phút"""
        if self.timer_thread and self.timer_thread.is_alive():
            self.timer_thread.cancel()
        
        self.timer_thread = threading.Timer(300.0, self._auto_save)  # 5 minutes = 300 seconds
        self.timer_thread.start()
        self.last_modified = datetime.now()
        
    def _auto_save(self):
        """Tự động lưu sau 5 phút"""
        if self.is_active:
            self.is_active = False
            # Gọi callback để lưu vào database
            print(f"🕰️ Auto-saving session {self.session_id} after timeout")
            
    def add_refinement(self, request: str, new_content: str):
        """Thêm một lần chỉnh sửa"""
        self.refinement_count += 1
        self.refinement_history.append({
            "refinement_id": self.refinement_count,
            "request": request,
            "content": new_content,
            "timestamp": datetime.now().isoformat()
        })
        self.content = new_content
        self.reset_timer()
        
    def stop_timer(self):
        """Dừng timer"""
        if self.timer_thread:
            self.timer_thread.cancel()
        self.is_active = False

class EnhancedChatAgent:
    def __init__(self, llm):
        self.client = llm
        self.active_sessions: Dict[str, InteractiveSession] = {}
        self.system_prompt = """
            Bạn là **EduMate** – một trợ lý ảo AI được thiết kế đặc biệt để hỗ trợ giáo viên trong việc tạo, chỉnh sửa và tinh chỉnh nội dung giảng dạy như bài giảng, giáo án, đề kiểm tra, kế hoạch học tập và các hoạt động học tập khác. 

            Bạn được tích hợp vào một hệ thống hỗ trợ giáo dục thông minh, phục vụ người dùng là giáo viên Việt Nam từ Tiểu học đến THPT. Mục tiêu chính của bạn là giúp giáo viên tiết kiệm thời gian, nâng cao chất lượng tài liệu dạy học, và cá nhân hóa nội dung theo mục tiêu giáo dục cụ thể như sau:  
            1. Giúp giáo viên nhanh chóng tạo nội dung giáo dục theo yêu cầu. 
            2. Hỗ trợ họ chỉnh sửa hoặc hoàn thiện nội dung đó. 
            3. Giải đáp các thắc mắc và hỗ trợ giáo viên trong quá trình giảng dạy.
            4. **Hỗ trợ chỉnh sửa tương tác trong thời gian thực với timer 5 phút**

            Bạn có thể hoạt động trong 4 chế độ chính tùy theo ngữ cảnh đầu vào: 

            **1. Chế độ "generate_prompt" – Chuyển yêu cầu từ form thành 1 câu lệnh tự nhiên**
            **2. Chế độ "refine_output" – Sửa, cải tiến hoặc mở rộng nội dung đã tạo**
            **3. Chế độ "assistant_chat" – Trò chuyện, tư vấn sư phạm, hỗ trợ chung**
            **4. Chế độ "interactive_refinement" – Chỉnh sửa tương tác với timer**

            ## Chế độ Interactive Refinement:
            - Khi người dùng yêu cầu chỉnh sửa nội dung đã tạo, bạn sẽ bắt đầu một phiên tương tác 5 phút
            - Thông báo rõ ràng về thời gian còn lại
            - Mỗi lần chỉnh sửa sẽ reset timer về 5 phút
            - Khuyến khích người dùng tiếp tục cải thiện trong thời gian này
            - Sau 5 phút không có tương tác, tự động lưu và kết thúc phiên

            ## Nguyên tắc chung: 
            1. Hãy lịch sự, rõ ràng, hỗ trợ đúng vai trò của một trợ lý giáo viên thông minh. 
            2. Ưu tiên ngắn gọn nhưng đủ ý, không nói vòng vo. 
            3. Luôn sử dụng thông tin người dùng cung cấp để phản hồi phù hợp. 
            4. Nếu thiếu thông tin, hãy hỏi lại hoặc đưa ra giả định hợp lý. 
            5. Luôn giữ văn phong sư phạm, dễ hiểu, thân thiện – phù hợp môi trường giáo dục.
            6. **Luôn thông báo về timer khi ở chế độ tương tác**

            ## Giọng điệu, ngôn ngữ và thái độ 
            - Luôn chuyên nghiệp, nhẹ nhàng, thân thiện. 
            - Tránh máy móc, lạnh lùng, kiểu chatbot. 
            - Ngôn ngữ gần gũi giáo viên, nhưng vẫn đúng chuẩn sư phạm. 
            - **Tích cực khuyến khích việc cải thiện nội dung trong thời gian tương tác**
        """

    def run(self, mode: str, user_input: str = "", form_data: dict = None, content: str = "", 
            instructions: str = "", session_id: str = None) -> dict:
        
        if mode == "interactive_refinement":
            return self._handle_interactive_refinement(session_id, user_input, content)
        elif mode == "start_interactive_session":
            return self._start_interactive_session(session_id, content, form_data.get("content_type", "lesson_plan"))
        else:
            # Các chế độ cũ
            return self._handle_traditional_modes(mode, user_input, form_data, content, instructions)
    
    def _handle_traditional_modes(self, mode: str, user_input: str, form_data: dict, content: str, instructions: str) -> dict:
        """Xử lý các chế độ truyền thống (không thay đổi logic cũ)"""
        messages = [{"role": "system", "content": self.system_prompt}]

        if mode == "generate_prompt":
            if not form_data:
                return {"error": "Thiếu dữ liệu form để tạo prompt."}
            prompt = self._build_prompt_from_form(form_data)
            messages.append({"role": "user", "content": prompt})

        elif mode == "generate_content":
            if not user_input:
                return {"error": "Thiếu yêu cầu tạo nội dung."}
            messages.append({"role": "user", "content": user_input})

        elif mode == "refine_output":
            if not content or not instructions:
                return {"error": "Thiếu nội dung gốc hoặc hướng dẫn chỉnh sửa."}
            refine_prompt = f"""Dưới đây là nội dung đã tạo:\n\n{content}\n\n---\n\nNgười dùng yêu cầu chỉnh sửa như sau: {instructions}\n\nHãy áp dụng yêu cầu và trả lại nội dung đã chỉnh sửa hoàn chỉnh."""
            messages.append({"role": "user", "content": refine_prompt})

        elif mode == "assistant_chat":
            if not user_input:
                return {"error": "Bạn cần nhập câu hỏi hoặc nội dung trò chuyện."}
            messages.append({"role": "user", "content": user_input})

        else:
            return {"error": f"Chế độ không hợp lệ: {mode}"}

        # Gọi LLM
        result = self.client.chat(messages, temperature=0.7)
        return {"response": result}

    def _start_interactive_session(self, session_id: str, content: str, content_type: str) -> dict:
        """Bắt đầu phiên tương tác 5 phút"""
        if not session_id:
            session_id = f"session_{int(time.time())}"
        
        # Tạo session mới
        session = InteractiveSession(session_id, content, content_type)
        session.reset_timer()
        self.active_sessions[session_id] = session
        
        content_type_name = "kế hoạch bài giảng" if content_type == "lesson_plan" else "quiz"
        
        response_message = f"""
🎯 **{content_type_name.title()} đã được tạo thành công!**

⏰ **Thời gian tương tác: 5 phút**
Bạn có **5 phút** để yêu cầu thêm bài tập, mở rộng lý thuyết, chỉnh sửa câu hỏi, hoặc bất kỳ cải tiến nào khác. 

💡 **Các yêu cầu bạn có thể đưa ra:**
- Thêm bài tập thực hành
- Mở rộng phần lý thuyết 
- Chỉnh sửa câu hỏi
- Thêm ví dụ minh họa
- Điều chỉnh độ khó
- Thêm hoạt động nhóm

⚡ **Mỗi lần bạn yêu cầu chỉnh sửa, timer sẽ được reset lại 5 phút.**

🤔 Bạn muốn điều chỉnh gì trong {content_type_name} này không?

*Sau 5 phút không có tương tác, nội dung sẽ được lưu tự động.*
        """
        
        return {
            "response": response_message.strip(),
            "session_id": session_id,
            "timer_active": True,
            "expires_at": (datetime.now() + timedelta(minutes=5)).isoformat()
        }

    def _handle_interactive_refinement(self, session_id: str, user_request: str, current_content: str = None) -> dict:
        """Xử lý yêu cầu chỉnh sửa trong phiên tương tác"""
        if not session_id or session_id not in self.active_sessions:
            return {"error": "Phiên tương tác không tồn tại hoặc đã hết hạn."}
        
        session = self.active_sessions[session_id]
        if not session.is_active:
            return {"error": "Phiên tương tác đã kết thúc."}
        
        # Lấy content hiện tại (từ session hoặc parameter)
        content_to_refine = current_content or session.content
        
        # Tạo prompt để chỉnh sửa
        refine_prompt = f"""
Dưới đây là nội dung hiện tại:

{content_to_refine}

---

Người dùng yêu cầu chỉnh sửa: {user_request}

Hãy áp dụng yêu cầu chỉnh sửa và trả lại toàn bộ nội dung đã được cải thiện. 
Chỉ thay đổi những phần được yêu cầu, giữ nguyên cấu trúc và phong cách tổng thể.
        """
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": refine_prompt}
        ]
        
        # Gọi LLM để chỉnh sửa
        refined_content = self.client.chat(messages, temperature=0.7)
        
        # Cập nhật session
        session.add_refinement(user_request, refined_content)
        
        content_type_name = "kế hoạch bài giảng" if session.content_type == "lesson_plan" else "quiz"
        
        response_message = f"""
✅ **Đã cập nhật {content_type_name} theo yêu cầu của bạn!**

🔄 **Thay đổi**: {user_request}
⏰ **Timer đã được reset**: Bạn có thêm **5 phút nữa** để tiếp tục chỉnh sửa
📊 **Số lần chỉnh sửa**: {session.refinement_count}

💡 **Bạn có muốn thêm điều gì khác không?**

*Timer sẽ tự động lưu sau 5 phút không có tương tác.*
        """
        
        return {
            "response": response_message.strip(),
            "refined_content": refined_content,
            "session_id": session_id,
            "timer_active": True,
            "expires_at": (datetime.now() + timedelta(minutes=5)).isoformat(),
            "refinement_count": session.refinement_count
        }

    def get_session_status(self, session_id: str) -> dict:
        """Lấy trạng thái của phiên tương tác"""
        if session_id not in self.active_sessions:
            return {"exists": False}
        
        session = self.active_sessions[session_id]
        time_remaining = 300 - (datetime.now() - session.last_modified).total_seconds()
        
        return {
            "exists": True,
            "is_active": session.is_active,
            "time_remaining": max(0, time_remaining),
            "refinement_count": session.refinement_count,
            "content_type": session.content_type,
            "expires_at": (session.last_modified + timedelta(minutes=5)).isoformat()
        }

    def end_session(self, session_id: str, save_to_db: bool = True) -> dict:
        """Kết thúc phiên tương tác và lưu"""
        if session_id not in self.active_sessions:
            return {"error": "Phiên không tồn tại"}
        
        session = self.active_sessions[session_id]
        session.stop_timer()
        
        # Lưu vào database (implement theo nhu cầu)
        if save_to_db:
            self._save_to_database(session)
        
        # Xóa khỏi memory
        del self.active_sessions[session_id]
        
        return {
            "message": f"Đã lưu {session.content_type} với {session.refinement_count} lần chỉnh sửa",
            "final_content": session.content,
            "refinement_history": session.refinement_history
        }

    def _save_to_database(self, session: InteractiveSession):
        """Lưu session vào database (cần implement theo DB của bạn)"""
        # TODO: Implement database saving logic
        print(f"💾 Saving session {session.session_id} to database")
        print(f"   Content type: {session.content_type}")
        print(f"   Refinements: {session.refinement_count}")
        print(f"   Created: {session.created_at}")
        print(f"   Last modified: {session.last_modified}")

    def _build_prompt_from_form(self, form_data: dict) -> str:
        """Giữ nguyên logic cũ"""
        grade = form_data.get("grade", "Không rõ")
        subject = form_data.get("subject", "")
        topic = form_data.get("topic", "")
        textbook = form_data.get("textbook", "")
        duration = form_data.get("duration", "")
        content_types = ", ".join(form_data.get("content_types", []))
        teaching_style = form_data.get("teaching_style", "")
        difficulty = form_data.get("difficulty", "")
        additional = form_data.get("additional_requirements", "")

        return f"""
            Tôi là giáo viên cần trợ giúp tạo nội dung giảng dạy.
                - Khối lớp: {grade}
                - Môn học: {subject}
                - Chủ đề: {topic}
                - Bộ sách giáo khoa: {textbook}
                - Thời lượng: {duration} phút
                - Loại nội dung: {content_types}
                - Phong cách giảng dạy: {teaching_style}
                - Mức độ khó: {difficulty}
                - Yêu cầu thêm: {additional}
            Hãy diễn đạt lại yêu cầu này thành một câu tự nhiên, rõ ràng và phù hợp để đưa vào hệ thống AI.
        """
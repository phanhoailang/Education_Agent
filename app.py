# app.py - FIXED VERSION
import os
import sys
import json
import tempfile
from uuid import uuid4
from pathlib import Path
from datetime import datetime
from typing import Optional
from modules.agents.EnhancedChatAgent import EnhancedChatAgent
from modules.slide_plan.SlidePipeline import SlidePipeline
from modules.agents.SlideContentWriterAgent import SlideContentWriterAgent

# === Đường dẫn tuyệt đối tới project / templates / static ===
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

sys.path.insert(0, str(BASE_DIR))

from flask import (
    Flask, render_template, render_template_string, request, redirect,
    url_for, session, send_from_directory, abort, jsonify
)
from jinja2 import TemplateNotFound

# Import pipeline + LLM client
from modules.quiz_plan.QuizPipeline import QuizPipeline
from utils.GPTClient import GPTClient
from graph_app.flow import run_flow

# ======== HTML Fallback tối thiểu ========
MINIMAL_FORM_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Edu Mate</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/form.css') }}"/>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css"/>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="header-content">
        <div class="logo"><div class="ai-icon">🤖</div><h1 class="title">Edu Mate</h1></div>
        <p class="subtitle">Trợ lý AI tạo kế hoạch giảng dạy & quiz</p>
      </div>
    </div>
    <div class="form-container">
      <form id="eduForm" method="POST" action="/process" enctype="multipart/form-data">
        <div class="form-grid">
          <div class="input-group">
            <label class="label" for="grade">Khối lớp*</label>
            <select class="select" id="grade" name="grade" required>
              <option value="">Chọn khối lớp</option>
              {% for i in range(1,13) %}<option value="{{ i }}">Lớp {{ i }}</option>{% endfor %}
            </select>
          </div>
          <div class="input-group">
            <label class="label" for="textbook">Bộ sách</label>
            <select class="select" id="textbook" name="textbook">
              <option value="">Chọn bộ sách</option>
              <option value="ketnoi">Kết nối tri thức</option>
              <option value="chantroi">Chân trời sáng tạo</option>
              <option value="canhdieu">Cánh Diều</option>
            </select>
          </div>
          <div class="input-group">
            <label class="label" for="subject">Môn học*</label>
            <input class="input" id="subject" name="subject" required placeholder="VD: Toán, Văn, Anh"/>
          </div>
          <div class="input-group">
            <label class="label" for="topic">Chủ đề*</label>
            <input class="input" id="topic" name="topic" required placeholder="VD: Phương trình bậc 2"/>
          </div>
          <div class="input-group">
            <label class="label" for="duration">Thời gian (phút)</label>
            <input type="number" class="input" id="duration" name="duration" min="15" max="180" placeholder="45"/>
          </div>
          <div class="input-group full-width">
            <label class="label">Loại nội dung*</label>
            <div class="checkbox-group">
              <label class="checkbox-item"><input type="checkbox" name="content_type[]" value="lesson_plan"/> <span>Kế hoạch giảng dạy</span></label>
              <label class="checkbox-item"><input type="checkbox" name="content_type[]" value="quiz"/> <span>Quiz</span></label>
              <label class="checkbox-item"><input type="checkbox" name="content_type[]" value="slide_plan"/> <span>Slide Plan</span></label>
            </div>
            <div class="error-message" id="content-error" style="display:none;">Vui lòng chọn ít nhất 1 loại nội dung</div>
          </div>
          <div class="input-group">
            <label class="label" for="teaching_style">Phong cách</label>
            <select class="select" id="teaching_style" name="teaching_style">
              <option value="">Chọn phong cách</option>
              <option value="interactive">Tương tác</option>
              <option value="visual">Trực quan</option>
              <option value="practical">Thực hành</option>
              <option value="traditional">Truyền thống</option>
              <option value="gamified">Gamification</option>
            </select>
          </div>
          <div class="input-group">
            <label class="label" for="difficulty">Mức độ</label>
            <select class="select" id="difficulty" name="difficulty">
              <option value="">Chọn mức độ</option>
              <option value="easy">Dễ</option>
              <option value="medium">Trung bình</option>
              <option value="hard">Khó</option>
              <option value="mixed">Hỗn hợp</option>
            </select>
          </div>
          <div class="input-group full-width">
            <label class="label" for="files">Đính kèm</label>
            <div class="file-upload" id="fileUpload">
              <input type="file" id="files" name="files[]" multiple accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.jpg,.png"/>
              <label class="file-upload-label" for="files"><span>Kéo thả hoặc click để chọn</span></label>
              <div class="file-list" id="fileList"></div>
            </div>
          </div>
          <div class="input-group full-width">
            <label class="label" for="additional_requirements">Yêu cầu bổ sung</label>
            <textarea class="textarea" id="additional_requirements" name="additional_requirements" placeholder="VD: thêm hoạt động nhóm, tập trung HS yếu…"></textarea>
          </div>
        </div>
        <button type="submit" class="submit-btn">🚀 Tạo nội dung giảng dạy với AI</button>
      </form>
    </div>
  </div>
  <script src="{{ url_for('static', filename='js/form.js') }}"></script>
</body>
</html>"""

def create_app():
    app = Flask(
        __name__,
        template_folder=str(TEMPLATES_DIR),
        static_folder=str(STATIC_DIR),
        static_url_path="/static",
    )
    app.secret_key = os.urandom(24).hex()
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    # Thư mục output
    output_dir = BASE_DIR / "output_lesson_plans"
    output_dir.mkdir(parents=True, exist_ok=True)
    quiz_output_dir = BASE_DIR / "output_quizzes"
    quiz_output_dir.mkdir(parents=True, exist_ok=True)
    slide_output_dir = BASE_DIR / "output_slides"
    slide_output_dir.mkdir(parents=True, exist_ok=True)

    app.config["OUTPUT_DIR"] = str(output_dir)
    app.config["QUIZ_OUTPUT_DIR"] = str(quiz_output_dir)
    app.config["SLIDE_OUTPUT_DIR"] = str(slide_output_dir)

    # ========= LLM & PIPELINE (Lazy) =========
    _quiz_pipeline = {"inst": None}
    _slide_pipeline = {"inst": None}

    def build_llm() -> GPTClient:
        """Tạo GPTClient với đầy đủ tham số và error handling"""
        api_key = os.environ.get("AZURE_API_KEY")
        endpoint = os.environ.get("AZURE_ENDPOINT") 
        model = os.environ.get("AZURE_MODEL")
        api_version = os.environ.get("AZURE_API_VERSION")
        
        # Kiểm tra các biến môi trường cần thiết
        missing_vars = []
        if not api_key:
            missing_vars.append("AZURE_API_KEY")
        if not endpoint:
            missing_vars.append("AZURE_ENDPOINT")
        if not model:
            missing_vars.append("AZURE_MODEL") 
        if not api_version:
            missing_vars.append("AZURE_API_VERSION")

        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        try:
            return GPTClient(
                api_key=api_key,
                endpoint=endpoint,
                model=model, 
                api_version=api_version
            )
        except Exception as e:
            raise Exception(f"Failed to initialize GPTClient: {str(e)}")

    def get_quiz_pipeline() -> "QuizPipeline":
        if _quiz_pipeline["inst"] is None:
            llm_client = build_llm()
            _quiz_pipeline["inst"] = QuizPipeline(llm_client)
        return _quiz_pipeline["inst"]

    def get_slide_pipeline() -> "SlidePipeline":
        if _slide_pipeline["inst"] is None:
            llm_client = build_llm()
            _slide_pipeline["inst"] = SlidePipeline(llm_client)
        return _slide_pipeline["inst"]

    # ========= Utils =========
    def read_text_file(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"[ERROR] Không đọc được file {path}: {e}")
            return ""

    def to_abs_path(maybe_rel_path: str) -> Optional[Path]:
        """Trả về Path tuyệt đối; nếu rỗng trả về None"""
        if not maybe_rel_path:
            return None
        p = Path(maybe_rel_path)
        return p if p.is_absolute() else (BASE_DIR / p).resolve()

    def slugify(s: str) -> str:
        import unicodedata, re as _re
        s = (s or "").strip().lower()
        s = unicodedata.normalize("NFD", s)
        s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
        s = _re.sub(r"[^a-z0-9]+", "_", s).strip("_")
        return s

    def find_latest_quiz(topic_hint: str = "", within_minutes: int = 10) -> Optional[Path]:
        """Tìm file .json mới nhất trong QUIZ_OUTPUT_DIR"""
        qdir = Path(app.config["QUIZ_OUTPUT_DIR"])
        files = sorted(qdir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return None
        
        # Ưu tiên theo topic
        hint = slugify(topic_hint)
        if hint:
            for f in files:
                if hint[:10] and hint.split("_")[0] in f.name.lower():
                    return f
        
        # Sau đó theo thời gian gần nhất
        now = datetime.now().timestamp()
        for f in files:
            if now - f.stat().st_mtime <= within_minutes * 60:
                return f
        
        # Cuối cùng: file mới nhất
        return files[0]

    def find_latest_slide(topic_hint: str = "", within_minutes: int = 10) -> Optional[Path]:
        """Tìm file slide mới nhất trong SLIDE_OUTPUT_DIR"""
        sdir = Path(app.config["SLIDE_OUTPUT_DIR"])
        
        # Tìm cả .md và .json files
        files = list(sdir.glob("*.json")) + list(sdir.glob("*.md"))
        files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
        
        if not files:
            print(f"[find_latest_slide] No slide files found in {sdir}")
            return None
        
        print(f"[find_latest_slide] Found {len(files)} slide files: {[f.name for f in files[:3]]}")
        
        # Ưu tiên theo topic
        hint = slugify(topic_hint)
        if hint:
            for f in files:
                if hint[:10] and hint.split("_")[0] in f.name.lower():
                    print(f"[find_latest_slide] Found topic match: {f.name}")
                    return f
        
        # Sau đó theo thời gian gần nhất
        now = datetime.now().timestamp()
        for f in files:
            if now - f.stat().st_mtime <= within_minutes * 60:
                print(f"[find_latest_slide] Found time match: {f.name}")
                return f
        
        # Cuối cùng: file mới nhất
        latest = files[0]
        print(f"[find_latest_slide] Using latest file: {latest.name}")
        return latest

    def find_quiz_md_pair(qjson_path: Path, qdata: dict) -> Optional[Path]:
        """Tìm file .md "cặp" với quiz JSON"""
        # 1) Theo key trong JSON
        for k in ("markdown_path", "md_path", "quiz_markdown_path"):
            p = qdata.get(k)
            if isinstance(p, str) and p.strip():
                try_path = Path(p)
                if not try_path.is_absolute():
                    try_path = (Path(app.config["QUIZ_OUTPUT_DIR"]) / try_path).resolve()
                if try_path.is_file():
                    return try_path
        # 2) Cùng stem
        cand1 = qjson_path.with_suffix(".md")
        if cand1.is_file():
            return cand1
        cand2 = Path(app.config["QUIZ_OUTPUT_DIR"]) / (qjson_path.stem + ".md")
        if cand2.is_file():
            return cand2
        return None

    def read_slide_content(slide_path: Path) -> dict:
        """Đọc nội dung slide từ file (.md hoặc .json)"""
        try:
            if slide_path.suffix.lower() == ".json":
                # File JSON - parse trực tiếp
                content = json.loads(slide_path.read_text(encoding="utf-8"))
                return content
            elif slide_path.suffix.lower() == ".md":
                # File Markdown - wrap trong object
                markdown_content = slide_path.read_text(encoding="utf-8")
                return {
                    "type": "markdown",
                    "content": markdown_content,
                    "filename": slide_path.name,
                    "slides": parse_markdown_slides(markdown_content)
                }
            else:
                return {"error": f"Unsupported slide file type: {slide_path.suffix}"}
        except Exception as e:
            print(f"[read_slide_content] Error reading {slide_path}: {e}")
            return {"error": f"Cannot read slide file: {str(e)}"}

    def parse_markdown_slides(markdown_content: str) -> list:
        """Parse markdown content thành danh sách slides"""
        try:
            # Split theo các heading level 1 hoặc 2
            import re
            slides = re.split(r'\n(?=#{1,2}\s)', markdown_content)
            
            # Clean up và format
            parsed_slides = []
            for i, slide in enumerate(slides):
                if slide.strip():
                    # Extract title (first line)
                    lines = slide.strip().split('\n')
                    title = lines[0].strip('#').strip() if lines else f"Slide {i+1}"
                    content = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ""
                    
                    parsed_slides.append({
                        "slide_number": i + 1,
                        "title": title,
                        "content": content
                    })
            
            return parsed_slides
        except Exception as e:
            print(f"[parse_markdown_slides] Error: {e}")
            return [{"slide_number": 1, "title": "Slide Content", "content": markdown_content}]

    # ========= Routes =========
    @app.route("/")
    def home():
        return redirect(url_for("form_page"))

    @app.route("/form")
    def form_page():
        try:
            return render_template("form.html")
        except TemplateNotFound:
            try:
                return render_template("index.html")
            except TemplateNotFound:
                return render_template_string(MINIMAL_FORM_HTML)
        except Exception as e:
            print("Error in /form:", repr(e))
            return {"error": "Lỗi render trang form", "details": str(e)}, 500

    @app.route("/process", methods=["POST"])
    def process():
        try:
            form_data_raw = request.form.to_dict(flat=True)
            content_types = request.form.getlist("content_type[]")
            files = request.files.getlist("files[]")

            print(f"🎯 [/process] Form data received: {form_data_raw}")
            print(f"🎯 [/process] Content types: {content_types}")
            print(f"🎯 [/process] Files: {[f.filename for f in files if f.filename]}")
            
            # Validation
            if not content_types:
                return jsonify({
                    "error": "Validation failed",
                    "details": "Vui lòng chọn ít nhất một loại nội dung"
                }), 400

            # Clear session keys
            session.pop("md_basename", None)
            session.pop("quiz_basename", None)
            session.pop("slide_basename", None)
            print("🗑️ Cleared all previous session data")

            # Lưu file tạm
            saved_files = []
            for file in files:
                if file and getattr(file, "filename", ""):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        file.save(tmp.name)
                        saved_files.append(tmp.name)

            # Tạo JSON data cho flow
            json_data = {
                "grade": form_data_raw.get("grade", ""),
                "textbook": form_data_raw.get("textbook", ""),
                "subject": form_data_raw.get("subject", ""),
                "topic": form_data_raw.get("topic", ""),
                "duration": form_data_raw.get("duration", ""),
                "content_types": content_types,
                "teaching_style": form_data_raw.get("teaching_style", ""),
                "difficulty": form_data_raw.get("difficulty", ""),
                "additional_requirements": form_data_raw.get("additional_requirements", ""),
                "files": saved_files,
                "timestamp": form_data_raw.get("timestamp", ""),
                
                # Config cho quiz
                "quiz_source": "material",
                "quiz_config": {
                    "difficulty": form_data_raw.get("difficulty", "medium"),
                    "question_count": 10,
                },
                
                # Config cho slide
                "slide_config": {
                    "color_scheme": "blue",
                    "export": {"pptx": True, "pdf": False},
                    "create_google_slides": True,
                    "tone": form_data_raw.get("teaching_style", "thân thiện")
                }
            }

            session["form_data"] = json_data
            print(f"💾 [/process] Saved to session: {json_data}")

            # Chạy pipeline
            print(f"\n🚀 Running flow with content_types: {content_types}")
            state = run_flow(json_data) or {}
            if not isinstance(state, dict):
                state = {}

            print(f"✅ Flow completed. State keys: {list(state.keys())}")

            # ====== XỬ LÝ KẾT QUẢ LESSON PLAN ======
            if "lesson_plan" in content_types:
                print("📘 Processing lesson plan result...")
                lesson_plan = state.get("lesson_plan") or {}
                md_path_pipeline = lesson_plan.get("markdown_path", "")
                md_path = to_abs_path(md_path_pipeline)
                output_dir = Path(app.config["OUTPUT_DIR"])

                if (md_path is None) or (not Path(md_path).exists()) or (not Path(md_path).is_file()):
                    print(f"[/process] markdown_path không sẵn có: {md_path_pipeline}")
                    complete_markdown = lesson_plan.get("complete_markdown", "")
                    fallback_name = f"lesson_{uuid4().hex}.md"
                    md_path = (output_dir / fallback_name).resolve()
                    try:
                        md_path.write_text(complete_markdown or "", encoding="utf-8")
                        print(f"[/process] Fallback -> đã ghi markdown vào: {md_path}")
                    except Exception as fe:
                        print(f"[/process] Fallback ERROR khi ghi file: {fe}")

                if md_path and Path(md_path).exists():
                    md_basename = Path(md_path).name
                    session["md_basename"] = md_basename
                    print(f"✅ Lesson plan saved: {md_basename}")
                else:
                    print("⚠️ Không thể lưu lesson plan")
            else:
                print("⭕ Skip lesson plan processing (not selected)")

            # ====== XỬ LÝ KẾT QUẢ QUIZ - FIXED ======
            if "quiz" in content_types:
                print("📝 Processing quiz result...")
                quiz_path = None
                
                # Tìm quiz từ state
                quiz_state = state.get("quiz") or {}
                
                # Kiểm tra các key có thể chứa đường dẫn quiz
                possible_keys = ["json_path", "output_path", "path", "file_path", "filepath", "file", "quiz_path", "quiz_file"]
                
                for key in possible_keys:
                    # Kiểm tra trong state gốc trước
                    value = state.get(key)
                    if not value:
                        # Kiểm tra trong quiz_state
                        value = quiz_state.get(key)
                    
                    if value and isinstance(value, str):
                        potential_path = to_abs_path(value)
                        if potential_path and potential_path.exists() and potential_path.suffix == ".json":
                            quiz_path = potential_path
                            print(f"✅ Found quiz file via key '{key}': {quiz_path}")
                            break
                
                # Nếu không tìm thấy từ state, tìm file mới nhất theo topic
                if not quiz_path:
                    print("🔍 Quiz path not found in state, searching for latest file...")
                    topic_hint = json_data.get("topic", "") or json_data.get("subject", "")
                    quiz_path = find_latest_quiz(topic_hint=topic_hint, within_minutes=15)
                    if quiz_path:
                        print(f"✅ Found quiz file by latest search: {quiz_path}")

                # Lưu quiz basename vào session
                if quiz_path and quiz_path.exists():
                    session["quiz_basename"] = quiz_path.name
                    print(f"✅ Quiz saved: {quiz_path.name}")
                    
                    # Debug: In ra thông tin chi tiết về quiz file
                    try:
                        with open(quiz_path, 'r', encoding='utf-8') as f:
                            quiz_data = json.load(f)
                            print(f"🔍 Quiz file content keys: {list(quiz_data.keys()) if isinstance(quiz_data, dict) else 'Not a dict'}")
                    except Exception as e:
                        print(f"❌ Error reading quiz file: {e}")
                else:
                    print("❌ Không tìm thấy quiz file")
                    # Debug: List all files in quiz directory
                    quiz_dir = Path(app.config["QUIZ_OUTPUT_DIR"])
                    if quiz_dir.exists():
                        all_quiz_files = list(quiz_dir.glob("*.json"))
                        print(f"📂 All quiz files in directory: {[f.name for f in all_quiz_files]}")
            else:
                print("⭕ Skip quiz processing (not selected)")

            # ====== XỬ LÝ KẾT QUẢ SLIDE PLAN - FIXED ======
            if "slide_plan" in content_types:
                print("📊 Processing slide plan result...")
                
                # Kiểm tra kết quả từ state
                slide_state = state.get("slide_plan") or {}
                slide_path = None
                
                # Tìm slide result từ state với nhiều key khả năng
                for k in ("json_path", "output_path", "path", "file_path", "filepath", "file", "slide_path", "slide_file", "markdown_path"):
                    v = slide_state.get(k)
                    if v:
                        p = to_abs_path(v)
                        if p and p.exists() and p.is_file():
                            slide_path = p
                            print(f"[slide_processing] Found slide via key '{k}': {p}")
                            break
                
                # Nếu chưa có slide từ flow, thử tìm file mới nhất
                if not slide_path:
                    print("📊 Searching for latest slide file...")
                    topic_hint = json_data.get("topic", "") or json_data.get("subject", "")
                    slide_path = find_latest_slide(topic_hint=topic_hint)

                # Nếu vẫn không có, thử tạo bằng pipeline trực tiếp
                if not slide_path:
                    print("📊 Creating slide plan directly...")
                    try:
                        # Lấy lesson plan để tạo slide
                        lesson_plan = state.get("lesson_plan", {})
                        if lesson_plan:
                            sp = get_slide_pipeline()
                            slide_result = sp.create_slide_from_lesson_plan(
                                lesson_plan_content=json.dumps(lesson_plan, ensure_ascii=False),
                                user_requirements=json_data.get("additional_requirements", ""),
                                slide_config=json_data.get("slide_config", {})
                            )
                            
                            if slide_result.get("success"):
                                slide_json_path = slide_result.get("json_path") or slide_result.get("markdown_path")
                                if slide_json_path:
                                    slide_path = Path(slide_json_path)
                                    print(f"✅ Slide created via pipeline: {slide_path}")
                            else:
                                print(f"❌ Slide creation failed: {slide_result.get('error')}")
                    except Exception as e:
                        print(f"❌ Error creating slide plan: {e}")

                if slide_path and slide_path.exists():
                    session["slide_basename"] = slide_path.name
                    print(f"✅ Slide plan saved: {slide_path.name}")
                else:
                    print("⚠️ Không tìm thấy slide plan file")
            else:
                print("⭕ Skip slide plan processing (not selected)")

            # ====== ĐIỀU HƯỚNG DỰA TRÊN CHOICE ======
            selected = set(content_types)
            print(f"🎯 Final redirect decision for: {selected}")
            
            # Always redirect to chat page to show results
            print("➡️ Redirect to chat page")
            return redirect(url_for("chat"))

        except Exception as e:
            print("❌ Error in /process:", str(e))
            import traceback
            traceback.print_exc()
            return jsonify({
                "error": "Lỗi xử lý form", 
                "details": str(e)
            }), 500

    @app.route("/chat")
    def chat():
        try:
            form_data = session.get("form_data", {})
            md_basename = session.get("md_basename", "")
            quiz_basename = session.get("quiz_basename", "")
            slide_basename = session.get("slide_basename", "")

            print(f"🔍 [/chat] Debug - form_data keys: {list(form_data.keys())}")
            print(f"🔍 [/chat] Debug - content_types: {form_data.get('content_types', [])}")
            print(f"🔍 [/chat] Debug - md_basename: {md_basename}")
            print(f"🔍 [/chat] Debug - quiz_basename: {quiz_basename}")
            print(f"🔍 [/chat] Debug - slide_basename: {slide_basename}")

            # ----- Lesson plan -----
            lesson_markdown = ""
            md_download_url = ""
            if md_basename:
                md_path = Path(app.config["OUTPUT_DIR"]) / md_basename
                if md_path.is_file():
                    lesson_markdown = read_text_file(md_path)
                    md_download_url = url_for("lesson_download", filename=md_basename)
                    print(f"[/chat] ✅ Lesson plan loaded: {len(lesson_markdown)} chars from {md_basename}")
                else:
                    print(f"[/chat] ❌ Lesson plan file not found: {md_path}")
            else:
                print("[/chat] ℹ️ No lesson plan in session")

            # ----- XỬ LÝ QUIZ - FIXED -----
            quiz_content = None
            quiz_download_url = ""
            if quiz_basename:
                qp = Path(app.config["QUIZ_OUTPUT_DIR"]) / quiz_basename
                print(f"[/chat] 🔍 Looking for quiz file: {qp}")
                
                if qp.is_file():
                    print(f"[/chat] 📝 Processing quiz file: {quiz_basename}")
                    # Đọc JSON
                    try:
                        qdata = json.loads(qp.read_text(encoding="utf-8"))
                        print(f"[/chat] ✅ Quiz JSON loaded successfully, keys: {list(qdata.keys()) if isinstance(qdata, dict) else 'Not a dict'}")
                        
                        # FIXED: Xử lý quiz content để gửi cho frontend
                        # Tìm markdown content trong JSON
                        quiz_markdown = None
                        possible_md_keys = ["complete_markdown", "markdown", "quiz_markdown", "content"]
                        
                        for key in possible_md_keys:
                            if key in qdata and isinstance(qdata[key], str) and qdata[key].strip():
                                quiz_markdown = qdata[key]
                                print(f"[/chat] ✅ Found quiz markdown in key '{key}': {len(quiz_markdown)} chars")
                                break
                        
                        if quiz_markdown:
                            # Gửi markdown content cho frontend
                            quiz_content = quiz_markdown
                        else:
                            # Fallback: gửi toàn bộ JSON object
                            quiz_content = qdata
                            
                    except Exception as e:
                        print(f"[/chat] ❌ Error reading quiz JSON: {e}")
                        qdata = {}
                        quiz_content = {}

                    # Tìm file .md cặp (nếu có)
                    md_pair = find_quiz_md_pair(qp, qdata)
                    if md_pair and md_pair.is_file():
                        try:
                            quiz_md = md_pair.read_text(encoding="utf-8")
                            quiz_content = quiz_md  # Ưu tiên markdown file
                            quiz_download_url = url_for("quiz_download_md", filename=md_pair.name)
                            print(f"[/chat] ✅ Quiz markdown file found: {len(quiz_md)} chars from {md_pair.name}")
                        except Exception as e:
                            print(f"[/chat] ❌ Cannot read quiz MD {md_pair}: {e}")
                    
                    # Set download URL
                    if not quiz_download_url:
                        quiz_download_url = url_for("quiz_download", filename=quiz_basename)
                        
                else:
                    print(f"[/chat] ❌ Quiz file not found: {qp}")
                    
                    # Thử tìm quiz file khác trong thư mục
                    quiz_dir = Path(app.config["QUIZ_OUTPUT_DIR"])
                    if quiz_dir.exists():
                        all_quiz_files = sorted(quiz_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
                        print(f"[/chat] 📂 Available quiz files: {[f.name for f in all_quiz_files[:5]]}")
                        
                        if all_quiz_files:
                            # Thử dùng file mới nhất
                            latest_quiz = all_quiz_files[0]
                            print(f"[/chat] 🔄 Trying latest quiz file: {latest_quiz.name}")
                            try:
                                qdata = json.loads(latest_quiz.read_text(encoding="utf-8"))
                                
                                # Tìm markdown content
                                quiz_markdown = None
                                for key in ["complete_markdown", "markdown", "quiz_markdown", "content"]:
                                    if key in qdata and isinstance(qdata[key], str) and qdata[key].strip():
                                        quiz_markdown = qdata[key]
                                        break
                                
                                quiz_content = quiz_markdown if quiz_markdown else qdata
                                session["quiz_basename"] = latest_quiz.name  # Update session
                                quiz_download_url = url_for("quiz_download", filename=latest_quiz.name)
                                print(f"[/chat] ✅ Loaded latest quiz file successfully")
                            except Exception as e:
                                print(f"[/chat] ❌ Error reading latest quiz: {e}")
            else:
                print("[/chat] ℹ️ No quiz in session")

            # ----- XỬ LÝ SLIDE CONTENT - FIXED -----
            slide_content = None
            slide_download_url = ""
            
            if slide_basename:
                sp = Path(app.config["SLIDE_OUTPUT_DIR"]) / slide_basename
                if sp.is_file():
                    print(f"[/chat] 📊 Processing slide file: {slide_basename}")
                    try:
                        # Sử dụng helper function để đọc slide
                        slide_data = read_slide_content(sp)
                        
                        # FIXED: Xử lý slide content để gửi cho frontend
                        if slide_data.get("type") == "markdown":
                            # Nếu là markdown file, gửi content
                            slide_content = slide_data.get("content", "")
                        elif isinstance(slide_data, dict) and "content" in slide_data:
                            # Nếu là JSON có content
                            slide_content = slide_data.get("content", "")
                        elif isinstance(slide_data, dict):
                            # Nếu là JSON object, tìm markdown content
                            possible_keys = ["markdown", "slide_markdown", "content", "complete_markdown"]
                            for key in possible_keys:
                                if key in slide_data and isinstance(slide_data[key], str) and slide_data[key].strip():
                                    slide_content = slide_data[key]
                                    break
                            
                            # Fallback: convert object to JSON string
                            if not slide_content:
                                slide_content = json.dumps(slide_data, ensure_ascii=False, indent=2)
                        else:
                            slide_content = str(slide_data)
                        
                        slide_download_url = url_for("slide_download", filename=slide_basename)
                        print(f"[/chat] ✅ Slide content loaded: {len(str(slide_content))} chars from {slide_basename}")
                    except Exception as e:
                        print(f"[/chat] ❌ Cannot read slide file {sp}: {e}")
                        slide_content = f"Error reading slide file: {str(e)}"
                else:
                    print(f"[/chat] ❌ Slide file not found: {sp}")
            else:
                # Kiểm tra xem có slide_plan trong content_types không
                content_types = form_data.get('content_types', [])
                if 'slide_plan' in content_types:
                    print("[/chat] 📊 Slide plan was requested but no file found")
                    slide_content = "Slide plan được yêu cầu nhưng chưa tạo thành công"
                else:
                    print("[/chat] ℹ️ No slide plan requested")
                    slide_content = ""

            # Debug final data
            print(f"[/chat] 📤 Sending to template:")
            print(f"   - lesson_markdown: {len(lesson_markdown)} chars")
            print(f"   - quiz_content: {type(quiz_content)} ({len(str(quiz_content)) if quiz_content else 0} chars)")
            print(f"   - slide_content: {type(slide_content)} ({len(str(slide_content)) if slide_content else 0} chars)")
            print(f"   - md_download_url: {md_download_url}")
            print(f"   - quiz_download_url: {quiz_download_url}")
            print(f"   - slide_download_url: {slide_download_url}")

            return render_template(
                "chat.html",
                form_data=form_data,
                lesson_markdown=lesson_markdown,
                md_download_url=md_download_url,
                quiz_content=quiz_content,
                quiz_download_url=quiz_download_url,
                slide_content=slide_content,
                slide_download_url=slide_download_url,
            )
        except TemplateNotFound as e:
            return {"error": "Lỗi render trang chat", "details": str(e)}, 500
        except Exception as e:
            print("❌ Error in /chat:", str(e))
            import traceback
            traceback.print_exc()
            return {"error": "Lỗi render trang chat", "details": str(e)}, 500

    @app.route("/quiz")
    def quiz_page():
        """Trang hiển thị quiz.html"""
        try:
            form_data = session.get("form_data", {})
            quiz_basename = session.get("quiz_basename", "")
            quiz_content = None
            quiz_download_url = ""

            if quiz_basename:
                qp = Path(app.config["QUIZ_OUTPUT_DIR"]) / quiz_basename
                if qp.is_file():
                    try:
                        quiz_content = json.loads(qp.read_text(encoding="utf-8"))
                        print(f"[/quiz] Render {quiz_basename}")
                    except Exception as e:
                        print(f"[/quiz] Không đọc được quiz {quiz_basename}: {e}")
                else:
                    print(f"[/quiz] Quiz file không tồn tại: {qp}")
            else:
                print("[/quiz] Chưa có quiz_basename trong session")

            return render_template(
                "quiz.html",
                form_data=form_data,
                quiz_content=quiz_content,
                quiz_download_url=quiz_download_url,
            )
        except TemplateNotFound as e:
            return {"error": "Lỗi render trang Quiz", "details": str(e)}, 500
        except Exception as e:
            print("❌ Error in /quiz:", str(e))
            return {"error": "Lỗi render trang Quiz", "details": str(e)}, 500

    @app.route("/lesson/download/<path:filename>")
    def lesson_download(filename):
        safe_name = os.path.basename(filename)
        file_path = Path(app.config["OUTPUT_DIR"]) / safe_name
        if not file_path.is_file():
            abort(404)
        return send_from_directory(
            Path(app.config["OUTPUT_DIR"]), safe_name, as_attachment=True, mimetype="text/markdown"
        )

    @app.route("/quiz/download/<path:filename>")
    def quiz_download(filename):
        """Giữ lại nếu bạn vẫn tải JSON ở nơi khác."""
        safe_name = os.path.basename(filename)
        file_path = Path(app.config["QUIZ_OUTPUT_DIR"]) / safe_name
        if not file_path.is_file():
            abort(404)
        return send_from_directory(
            Path(app.config["QUIZ_OUTPUT_DIR"]),
            safe_name,
            as_attachment=True,
            mimetype="application/json"
        )

    @app.route("/quiz/download-md/<path:filename>")
    def quiz_download_md(filename):
        """Tải quiz ở dạng Markdown."""
        safe_name = os.path.basename(filename)
        file_path = Path(app.config["QUIZ_OUTPUT_DIR"]) / safe_name
        if not file_path.is_file():
            abort(404)
        return send_from_directory(
            Path(app.config["QUIZ_OUTPUT_DIR"]),
            safe_name,
            as_attachment=True,
            mimetype="text/markdown"
        )

    @app.route("/slide/download/<path:filename>")
    def slide_download(filename):
        """Tải slide file (.md, .html, .json...)."""
        safe_name = os.path.basename(filename)
        file_path = Path(app.config["SLIDE_OUTPUT_DIR"]) / safe_name
        if not file_path.is_file():
            abort(404)

        # Xác định MIME type dựa vào phần mở rộng
        ext = file_path.suffix.lower()
        if ext == ".md":
            mimetype = "text/markdown"
        elif ext == ".html":
            mimetype = "text/html"
        elif ext == ".json":
            mimetype = "application/json"
        else:
            mimetype = "application/octet-stream"

        return send_from_directory(
            Path(app.config["SLIDE_OUTPUT_DIR"]),
            safe_name,
            as_attachment=True,
            mimetype=mimetype,
        )

    @app.route("/api/slide/latest")
    def api_slide_latest():
        """API endpoint để lấy slide mới nhất"""
        try:
            form_data = session.get("form_data", {})
            topic_hint = form_data.get("topic", "") or form_data.get("subject", "")
            
            slide_path = find_latest_slide(topic_hint=topic_hint)
            if not slide_path:
                return jsonify({"error": "No slide found"}), 404
            
            slide_content = read_slide_content(slide_path)
            return jsonify({
                "success": True,
                "content": slide_content,
                "filename": slide_path.name,
                "download_url": url_for("slide_download", filename=slide_path.name)
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/slide/latest")
    def slide_latest_redirect():
        """Redirect to API endpoint"""
        return redirect(url_for("api_slide_latest"))

    @app.route("/output_slides/latest")
    def output_slides_latest():
        """Fallback endpoint để tương thích"""
        return redirect(url_for("api_slide_latest"))

    @app.route("/generate_quiz", methods=["POST"])
    def generate_quiz():
        try:
            if request.is_json:
                data = request.get_json(silent=True) or {}
                user_prompt = data.get("prompt", "")
                chunks = data.get("chunks", [])
            else:
                user_prompt = request.form.get("prompt", "")
                chunks_raw = request.form.get("chunks", "[]")
                try:
                    chunks = json.loads(chunks_raw) if isinstance(chunks_raw, str) else (chunks_raw or [])
                except Exception:
                    chunks = []

            qp = get_quiz_pipeline()
            result = qp.create_full_quiz(user_prompt, chunks)
            status = 200 if "error" not in result else 400

            # Nếu pipeline trả về đường dẫn file, giữ vào session để UI dùng luôn
            quiz_file = result.get("output_path") or result.get("json_path") or result.get("file")
            if quiz_file:
                p = Path(quiz_file)
                if p.exists():
                    session["quiz_basename"] = p.name

            return jsonify(result), status
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route("/generate_slide", methods=["POST"])
    def generate_slide():
        try:
            if request.is_json:
                data = request.get_json(silent=True) or {}
                user_prompt = data.get("prompt", "")
                lesson_plan = data.get("lesson_plan", {})
                slide_config = data.get("slide_config", {})
            else:
                user_prompt = request.form.get("prompt", "")
                lesson_plan_raw = request.form.get("lesson_plan", "{}")
                slide_config_raw = request.form.get("slide_config", "{}")
                try:
                    lesson_plan = json.loads(lesson_plan_raw) if isinstance(lesson_plan_raw, str) else (lesson_plan_raw or {})
                    slide_config = json.loads(slide_config_raw) if isinstance(slide_config_raw, str) else (slide_config_raw or {})
                except Exception:
                    lesson_plan = {}
                    slide_config = {}

            sp = get_slide_pipeline()
            result = sp.create_slide_from_lesson_plan(
                lesson_plan_content=json.dumps(lesson_plan, ensure_ascii=False) if lesson_plan else user_prompt,
                user_requirements=user_prompt,
                slide_config=slide_config
            )
            status = 200 if result.get("success") else 400

            # Nếu pipeline trả về đường dẫn file, giữ vào session
            slide_file = result.get("json_path") or result.get("markdown_path")
            if slide_file:
                p = Path(slide_file)
                if p.exists():
                    session["slide_basename"] = p.name

            return jsonify(result), status
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e), "success": False}), 500

    return app


def find_free_port(preferred=5000):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


app = create_app()

if __name__ == "__main__":
    # Tự động chọn cổng trống; có thể đặt PORT=5050 để chỉ định
    port = int(os.getenv("PORT", "0")) or find_free_port(5000)
    print("=== Flask starting ===")
    print("BASE_DIR      :", Path(__file__).resolve().parent)
    print("TEMPLATES_DIR :", TEMPLATES_DIR, "| exists:", TEMPLATES_DIR.is_dir())
    print("STATIC_DIR    :", STATIC_DIR, "| exists:", STATIC_DIR.is_dir())
    print(f"▶️ Open: http://127.0.0.1:{port}/form   (hoặc /)")
    app.run(debug=True, use_reloader=False, port=port)
    
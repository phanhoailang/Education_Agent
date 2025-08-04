# app.py
import os
import sys
import json
import tempfile
from uuid import uuid4
from pathlib import Path

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
from modules.lesson_plan.QuizPipeline import QuizPipeline
from utils.GPTClient import GPTClient
from graph_app.flow import run_flow

# ======== HTML Fallback tối thiểu (để không bao giờ lỗi nếu thiếu file) ========
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
    app.config["TEMPLATES_AUTO_RELOAD"] = True  # auto reload khi chỉnh html

    # Thư mục output
    output_dir = BASE_DIR / "output_lesson_plans"
    output_dir.mkdir(parents=True, exist_ok=True)
    quiz_output_dir = BASE_DIR / "output_quizzes"
    quiz_output_dir.mkdir(parents=True, exist_ok=True)

    app.config["OUTPUT_DIR"] = str(output_dir)
    app.config["QUIZ_OUTPUT_DIR"] = str(quiz_output_dir)

    # ========= LLM & PIPELINE (Lazy) =========
    _quiz_pipeline = {"inst": None}

    def build_llm() -> GPTClient:
        return GPTClient()

    def get_quiz_pipeline() -> "QuizPipeline":
        if _quiz_pipeline["inst"] is None:
            llm_client = build_llm()
            _quiz_pipeline["inst"] = QuizPipeline(llm_client)
        return _quiz_pipeline["inst"]

    # ========= Utils =========
    def read_text_file(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"[ERROR] Không đọc được file {path}: {e}")
            return ""

    def to_abs_path(maybe_rel_path: str):
        """Trả về Path tuyệt đối; nếu rỗng trả về None (tránh Path('') == '.')"""
        if not maybe_rel_path:
            return None
        p = Path(maybe_rel_path)
        return p if p.is_absolute() else (BASE_DIR / p).resolve()

    # ========= Debug helper =========
    @app.route("/_debug/where")
    def debug_where():
        data = {
            "BASE_DIR": str(BASE_DIR),
            "TEMPLATES_DIR": str(TEMPLATES_DIR),
            "STATIC_DIR": str(STATIC_DIR),
            "exists": {
                "templates_dir": TEMPLATES_DIR.is_dir(),
                "static_dir": STATIC_DIR.is_dir(),
                "form_html": (TEMPLATES_DIR / "form.html").is_file(),
                "index_html": (TEMPLATES_DIR / "index.html").is_file(),
                "chat_html": (TEMPLATES_DIR / "chat.html").is_file(),
                "lessonplan_html": (TEMPLATES_DIR / "lessonplan.html").is_file(),
            },
            "templates_list": [],
            "static_css_list": [],
            "static_js_list": [],
        }
        try:
            data["templates_list"] = sorted(os.listdir(TEMPLATES_DIR))
        except Exception as e:
            data["templates_list"] = [f"<error: {e}>"]

        try:
            data["static_css_list"] = sorted(os.listdir(STATIC_DIR / "css"))
        except Exception as e:
            data["static_css_list"] = [f"<error: {e}>"]

        try:
            data["static_js_list"] = sorted(os.listdir(STATIC_DIR / "js"))
        except Exception as e:
            data["static_js_list"] = [f"<error: {e}>"]

        return jsonify(data)

    # ===== Installer: tạo file templates/form.html đúng chỗ nếu bạn muốn =====
    @app.route("/_debug/install_form")
    def install_form():
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        target = TEMPLATES_DIR / "form.html"
        try:
            target.write_text(MINIMAL_FORM_HTML, encoding="utf-8")
            return {"ok": True, "created": str(target)}
        except Exception as e:
            return {"ok": False, "error": str(e), "where": str(target)}, 500

    # ========= Routes =========
    @app.route("/")
    def home():
        """Redirect sang /form để đồng nhất flow."""
        return redirect(url_for("form_page"))

    @app.route("/form")
    def form_page():
        """
        Thứ tự ưu tiên:
        1) form.html
        2) index.html
        3) Fallback inline (không cần file)
        """
        try:
            return render_template("form.html")
        except TemplateNotFound:
            try:
                return render_template("index.html")
            except TemplateNotFound:
                # Fallback cuối: inline HTML
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

            # Lưu file tạm (để flow xử lý)
            saved_files = []
            for file in files:
                if file and getattr(file, "filename", ""):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        file.save(tmp.name)
                        saved_files.append(tmp.name)

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
            }

            session["form_data"] = json_data
            print("[/process] form_data:", json_data)

            state = run_flow(json_data) or {}
            if not isinstance(state, dict):
                state = {}

            lesson_plan = state.get("lesson_plan") or {}
            md_path_pipeline = lesson_plan.get("markdown_path", "")
            md_path = to_abs_path(md_path_pipeline)

            output_dir = Path(app.config["OUTPUT_DIR"])

            # Bắt buộc là file tồn tại thật sự
            if (md_path is None) or (not Path(md_path).exists()) or (not Path(md_path).is_file()):
                print(f"[/process] markdown_path không sẵn có/không phải file: {md_path_pipeline}")
                complete_markdown = lesson_plan.get("complete_markdown", "")
                fallback_name = f"lesson_{uuid4().hex}.md"
                md_path = (output_dir / fallback_name).resolve()
                try:
                    md_path.write_text(complete_markdown or "", encoding="utf-8")
                    print(f"[/process] Fallback -> đã ghi markdown vào: {md_path}")
                except Exception as fe:
                    print(f"[/process] Fallback ERROR khi ghi file: {fe}")

            md_basename = Path(md_path).name
            session["md_basename"] = md_basename
            print(f"[/process] md_basename lưu vào session: {md_basename}")

            return redirect(url_for("chat"))

        except Exception as e:
            print("❌ Error in /process:", str(e))
            return {"error": "Lỗi xử lý form", "details": str(e)}, 500

    @app.route("/chat")
    def chat():
        try:
            form_data = session.get("form_data", {})
            md_basename = session.get("md_basename", "")

            lesson_markdown = ""
            md_download_url = ""

            if md_basename:
                md_path = Path(app.config["OUTPUT_DIR"]) / md_basename
                if md_path.is_file():
                    lesson_markdown = read_text_file(md_path)
                    md_download_url = url_for("lesson_download", filename=md_basename)
                    print(f"[/chat] Sẽ hiển thị Markdown len={len(lesson_markdown)} từ {md_path}")
                else:
                    print(f"[/chat] File markdown không tồn tại: {md_path}")
            else:
                print("[/chat] Chưa có md_basename trong session")

            return render_template(
                "chat.html",
                form_data=form_data,
                lesson_markdown=lesson_markdown,
                md_download_url=md_download_url,
            )
        except TemplateNotFound as e:
            return {"error": "Lỗi render trang chat", "details": str(e)}, 500
        except Exception as e:
            print("❌ Error in /chat:", str(e))
            return {"error": "Lỗi render trang chat", "details": str(e)}, 500

    @app.route("/lesson-plan")
    def lesson_plan_page():
        try:
            return render_template("lessonplan.html")
        except TemplateNotFound as e:
            return {"error": "Lỗi render trang LessonPlan", "details": str(e)}, 500
        except Exception as e:
            print("❌ Error in /lesson-plan:", str(e))
            return {"error": "Lỗi render trang LessonPlan", "details": str(e)}, 500

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
        safe_name = os.path.basename(filename)
        file_path = Path(app.config["QUIZ_OUTPUT_DIR"]) / safe_name
        if not file_path.is_file():
            abort(404)
        return send_from_directory(
            Path(app.config["QUIZ_OUTPUT_DIR"]), safe_name, as_attachment=True, mimetype="text/markdown"
        )

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
            return jsonify(result), status
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

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
    print(f"▶︎ Open: http://127.0.0.1:{port}/form   (hoặc /)")
    app.run(debug=True, use_reloader=False, port=port)

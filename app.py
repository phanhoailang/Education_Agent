# app.py
import os
import tempfile
from uuid import uuid4
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, send_from_directory, abort
)

# HÀM chạy flow của bạn (đÃ return state)
from graph_app.flow import run_flow

# =========================
#  CẤU HÌNH ỨNG DỤNG
# =========================
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.urandom(24).hex()  # Secret key cho session

# Thư mục lưu kết quả lesson plan từ pipeline
OUTPUT_DIR = os.path.abspath(os.path.join(os.getcwd(), "output_lesson_plans"))
os.makedirs(OUTPUT_DIR, exist_ok=True)


# =========================
#  TIỆN ÍCH
# =========================
def read_text_file(path: str) -> str:
    """Đọc nội dung text (UTF-8); trả về '' nếu lỗi."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"[ERROR] Không đọc được file {path}: {e}")
        return ""


def to_abs_path(maybe_rel_path: str) -> str:
    """Trả về đường dẫn tuyệt đối từ đường dẫn trả về bởi pipeline."""
    if not maybe_rel_path:
        return ""
    if os.path.isabs(maybe_rel_path):
        return maybe_rel_path
    # Nếu pipeline trả về tương đối, quy chiếu theo project root hiện tại
    return os.path.abspath(os.path.join(os.getcwd(), maybe_rel_path))


# =========================
#  ROUTES
# =========================
@app.route("/")
def home():
    """Trang chủ (form nhập)."""
    try:
        return render_template("index.html")
    except Exception as e:
        print("Error in /:", str(e))
        return {"error": "Lỗi render trang index", "details": str(e)}, 500


@app.route("/process", methods=["POST"])
def process():
    """
    1) Lấy dữ liệu từ form + file đính kèm
    2) Gọi run_flow(form_data) để sinh lesson plan
    3) Lấy markdown từ 'markdown_path' (fallback: 'complete_markdown')
    4) Lưu chỉ basename .md vào session, redirect sang /chat
    """
    try:
        # 1) Lấy dữ liệu từ form
        form_data_raw = request.form.to_dict(flat=True)
        content_types = request.form.getlist('content_type[]')  # nếu form dùng content_type[]
        files = request.files.getlist('files[]')

        # 2) Lưu file đính kèm tạm (chỉ cần đường dẫn để pipeline xử lý)
        saved_files = []
        for file in files:
            if file and getattr(file, "filename", ""):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    file.save(tmp.name)
                    saved_files.append(tmp.name)

        # 3) Chuẩn hóa dữ liệu gửi qua flow
        json_data = {
            'grade': form_data_raw.get('grade', ''),
            'textbook': form_data_raw.get('textbook', ''),
            'subject': form_data_raw.get('subject', ''),
            'topic': form_data_raw.get('topic', ''),
            'duration': form_data_raw.get('duration', ''),
            'content_types': content_types,
            'teaching_style': form_data_raw.get('teaching_style', ''),
            'difficulty': form_data_raw.get('difficulty', ''),
            'additional_requirements': form_data_raw.get('additional_requirements', ''),
            'files': saved_files,
            'timestamp': form_data_raw.get('timestamp', '')
        }

        # Lưu form data (ngắn, an toàn) vào session để UI hiển thị xác nhận
        session['form_data'] = json_data
        print("[/process] form_data:", json_data)

        # 4) Gọi flow và nhận state
        state = run_flow(json_data) or {}
        if not isinstance(state, dict):
            state = {}

        lesson_plan = state.get("lesson_plan") or {}
        md_path_pipeline = lesson_plan.get("markdown_path", "")
        md_path = to_abs_path(md_path_pipeline)

        # 5) Nếu có file .md do pipeline tạo sẵn, sử dụng; nếu không, fallback từ complete_markdown
        if not md_path or not os.path.exists(md_path):
            print(f"[/process] markdown_path không sẵn có: {md_path_pipeline}")
            complete_markdown = lesson_plan.get("complete_markdown", "")
            # Dù complete_markdown rỗng, vẫn tạo file để UI có đường dẫn rõ ràng
            fallback_name = f"lesson_{uuid4().hex}.md"
            md_path = os.path.join(OUTPUT_DIR, fallback_name)
            try:
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(complete_markdown or "")
                print(f"[/process] Fallback -> đã ghi markdown vào: {md_path}")
            except Exception as fe:
                print(f"[/process] Fallback ERROR khi ghi file: {fe}")

        # 6) Lưu chỉ basename vào session (tránh cookie lớn)
        md_basename = os.path.basename(md_path)
        session['md_basename'] = md_basename
        print(f"[/process] md_basename lưu vào session: {md_basename}")
        print(f"[/process] CHỌN md_path = {md_path}")
        print(f"[/process] md_basename = {md_basename}")


        # 7) Chuyển sang trang chat
        return redirect(url_for("chat"))

    except Exception as e:
        print("❌ Error in /process:", str(e))
        return {"error": "Lỗi xử lý form", "details": str(e)}, 500


@app.route("/chat")
def chat():
    """
    Đọc tên file .md từ session, mở file và render nội dung ra UI.
    Đồng thời cấp link tải .md qua route /lesson/download/<filename>.
    """
    try:
        form_data = session.get("form_data", {})
        md_basename = session.get("md_basename", "")

        lesson_markdown = ""
        md_download_url = ""

        if md_basename:
            md_path = os.path.join(OUTPUT_DIR, os.path.basename(md_basename))
            lesson_markdown = read_text_file(md_path)
            md_download_url = url_for("lesson_download", filename=os.path.basename(md_basename))
            print(f"[/chat] Sẽ hiển thị Markdown len={len(lesson_markdown)} từ {md_path}")
        else:
            print("[/chat] Chưa có md_basename trong session")

        # Truyền dữ liệu sang template (để <script type="application/json"> parse trong JS)
        return render_template(
            "chat.html",
            form_data=form_data,
            lesson_markdown=lesson_markdown,
            md_download_url=md_download_url
        )
    except Exception as e:
        print("❌ Error in /chat:", str(e))
        return {"error": "Lỗi render trang chat", "details": str(e)}, 500


@app.route("/lesson/download/<path:filename>")
def lesson_download(filename):
    """
    Cho phép tải file Markdown theo tên file; chỉ phục vụ file nằm trong OUTPUT_DIR.
    """
    safe_name = os.path.basename(filename)  # tránh path traversal
    file_path = os.path.join(OUTPUT_DIR, safe_name)
    if not os.path.isfile(file_path):
        abort(404)
    return send_from_directory(OUTPUT_DIR, safe_name, as_attachment=True, mimetype="text/markdown")


# =========================
#  MAIN
# =========================
if __name__ == "__main__":
    # Dùng use_reloader=False để tránh chạy 2 process (ảnh hưởng tới state / debug)
    app.run(debug=True, use_reloader=False, port=5000)

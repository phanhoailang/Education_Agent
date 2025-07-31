from flask import Flask, render_template, request, redirect, url_for, session
from graph_app.flow import run_flow
import tempfile
import os

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.urandom(24).hex()  # Tạo secret key ngẫu nhiên

@app.route('/')
def home():
    try:
        return render_template('index.html')
    except Exception as e:
        print("Error in /:", str(e))
        return {"error": "Lỗi render trang index", "details": str(e)}, 500

@app.route('/process', methods=['POST'])
def process():
    try:
        # Lấy dữ liệu từ form
        form_data = request.form.to_dict(flat=True)
        content_types = request.form.getlist('content_type[]')
        files = request.files.getlist('files[]')

        # Lưu file đính kèm
        saved_files = []

        for file in files:
            if file.filename:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    file.save(tmp.name)
                    saved_files.append(tmp.name)

        # Tạo JSON từ form
        json_data = {
            'grade': form_data.get('grade', ''),
            'textbook': form_data.get('textbook', ''),
            'subject': form_data.get('subject', ''),
            'topic': form_data.get('topic', ''),
            'duration': form_data.get('duration', ''),
            'content_types': content_types,
            'teaching_style': form_data.get('teaching_style', ''),
            'difficulty': form_data.get('difficulty', ''),
            'additional_requirements': form_data.get('additional_requirements', ''),
            'files': saved_files,
            'timestamp': form_data.get('timestamp', '')
        }

        # Lưu vào session
        session['form_data'] = json_data
        print("Form data saved to session:", json_data)

        # ✅ Gọi flow xử lý 1 lần duy nhất
        run_flow(json_data)

        # Sau khi xử lý xong, chuyển sang trang chat
        return redirect(url_for('chat'))

    except Exception as e:
        print("Error in /process:", str(e))
        return {"error": "Lỗi xử lý form", "details": str(e)}, 500

@app.route('/chat')
def chat():
    try:
        form_data = session.get('form_data', {})
        print("Rendering chat with form_data:", form_data)
        return render_template('chat.html', form_data=form_data)
    except Exception as e:
        print("Error in /chat:", str(e))
        return {"error": "Lỗi render trang chat", "details": str(e)}, 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
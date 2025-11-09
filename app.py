import os
from functools import wraps
from flask import Flask, request, jsonify, render_template, send_file, Response, session, redirect, url_for, stream_with_context
from youtube_qa_app import YouTubeQAApp

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Set a secret key for session management

# Create an instance of YouTubeQAApp
youtube_qa = YouTubeQAApp()

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == os.getenv('AUTH_USERNAME') and password == os.getenv('AUTH_PASSWORD'):
            session['logged_in'] = True
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def home():
    default_video_url = os.getenv('DEFAULT_VIDEO_URL', '')
    offline_mode = os.getenv('OFFLINE_MODE', '0').lower() in ('1','true','yes')
    return render_template('index.html', default_video_url=default_video_url, offline_mode=offline_mode)

@app.route('/load_video', methods=['POST'])
@login_required
def load_video():
    youtube_url = request.json.get('youtube_url')

    def generate():
        for progress in youtube_qa.process_video(youtube_url):
            if isinstance(progress, tuple):
                if progress[0] == 'download':
                    yield f"download:{progress[1]}\n"
                elif progress[0] == 'transcribe':
                    yield f"transcribe:{progress[1]}\n"
            elif progress == "done":
                yield "done\n"
            else:
                yield f"{progress}\n"

    return Response(stream_with_context(generate()), content_type='text/plain')

@app.route('/ask_stream')
@login_required
def ask_question_stream():
    youtube_url = request.args.get('youtube_url')
    question = request.args.get('question')
    user_info = {
        "participant_id": request.args.get('participant_id', ''),
        "work_status": request.args.get('work_status', 'N/A'),
        "gender": request.args.get('gender', 'N/A')
    }

    def generate():
        for chunk in youtube_qa.process_question_stream(youtube_url, question, user_info):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return Response(generate(), content_type='text/event-stream')

@app.route('/feedback', methods=['POST'])
@login_required
def submit_feedback():
    data = request.json
    if not data or 'feedback' not in data:
        return jsonify({"error": "Missing feedback"}), 400

    feedback = data['feedback']
    result = youtube_qa.submit_feedback(feedback)
    return jsonify(result)

@app.route('/admin')
@login_required
def admin():
    return render_template('admin.html')

@app.route('/admin/download_csv')
@login_required
def download_csv():
    csv_path = "qa_feedback_log.csv"
    if os.path.exists(csv_path):
        return send_file(csv_path, as_attachment=True, download_name="qa_feedback_log.csv")
    else:
        return jsonify({"error": "CSV file not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)
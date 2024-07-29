import os
from functools import wraps

from flask import Flask, request, jsonify, render_template, send_file, Response, session, redirect, url_for

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
    return render_template('index.html')


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


@app.route('/admin/reset_csv', methods=['POST'])
@login_required
def reset_csv():
    csv_path = "qa_feedback_log.csv"
    try:
        if os.path.exists(csv_path):
            os.remove(csv_path)
        # Create a new CSV file with headers
        youtube_qa.create_new_csv()
        return jsonify({"message": "CSV file has been reset successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
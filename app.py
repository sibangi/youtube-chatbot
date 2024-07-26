import os

from flask import Flask, request, jsonify, render_template, send_file

from youtube_qa_app import YouTubeQAApp

app = Flask(__name__)

# Create an instance of YouTubeQAApp
youtube_qa = YouTubeQAApp()


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/ask', methods=['POST'])
def ask_question():
    data = request.json
    if not data or 'youtube_url' not in data or 'question' not in data:
        return jsonify({"error": "Missing youtube_url or question"}), 400

    youtube_url = data['youtube_url']
    question = data['question']
    user_info = {
        "nickname": data.get('nickname', 'Anonymous'),
        "work_status": data.get('work_status', 'N/A'),
        "gender": data.get('gender', 'N/A')
    }

    result = youtube_qa.process_question_headless(youtube_url, question, user_info)
    return jsonify(result)


@app.route('/feedback', methods=['POST'])
def submit_feedback():
    data = request.json
    if not data or 'feedback' not in data:
        return jsonify({"error": "Missing feedback"}), 400

    feedback = data['feedback']
    result = youtube_qa.submit_feedback(feedback)
    return jsonify(result)


@app.route('/download_csv')
def download_csv():
    csv_path = "qa_feedback_log.csv"
    if os.path.exists(csv_path):
        return send_file(csv_path, as_attachment=True, download_name="qa_feedback_log.csv")
    else:
        return jsonify({"error": "CSV file not found"}), 404


if __name__ == '__main__':
    app.run(debug=True)

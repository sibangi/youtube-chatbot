import os

from flask import Flask, request, jsonify, render_template, send_file, Response

from youtube_qa_app import YouTubeQAApp

app = Flask(__name__)

# Create an instance of YouTubeQAApp
youtube_qa = YouTubeQAApp()


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/ask_stream')
def ask_question_stream():
    youtube_url = request.args.get('youtube_url')
    question = request.args.get('question')
    user_info = {
        "first_name": request.args.get('first_name', ''),
        "last_name": request.args.get('last_name', ''),
        "work_status": request.args.get('work_status', 'N/A'),
        "gender": request.args.get('gender', 'N/A')
    }

    def generate():
        for chunk in youtube_qa.process_question_stream(youtube_url, question, user_info):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return Response(generate(), content_type='text/event-stream')


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


@app.route('/reset_csv', methods=['POST'])
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

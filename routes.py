from flask import Flask, render_template, request, jsonify

from app import create_app

flask_app = Flask(__name__)


@flask_app.route('/')
def index():
    return render_template('index.html')


@flask_app.route('/api/ask_question', methods=['POST'])
def ask_question():
    data = request.json
    question = data.get('question')
    youtube_url = data.get('youtube_url')

    # Here you would interact with your PyQt5 app
    pyqt_app = create_app()
    # You'll need to modify your YouTubeQAApp class to have methods
    # that can be called without showing the GUI
    result = pyqt_app.process_question_headless(youtube_url, question)

    return jsonify(result)


if __name__ == '__main__':
    flask_app.run(debug=True)

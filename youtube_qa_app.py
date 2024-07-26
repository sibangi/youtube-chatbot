import sys
import re
import csv
import os
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
                             QTextEdit, QLabel, QComboBox, QMessageBox, QProgressBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPalette, QColor
from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI


class TranscriptLoader(QThread):
    finished = pyqtSignal(str)

    def __init__(self, video_id):
        QThread.__init__(self)
        self.video_id = video_id

    def run(self):
        try:
            transcript = YouTubeTranscriptApi.get_transcript(self.video_id)
            transcript_text = " ".join([entry['text'] for entry in transcript])
            self.finished.emit(transcript_text)
        except Exception as e:
            self.finished.emit(f"Error: {str(e)}")


class YouTubeQAApp(QWidget):
    def __init__(self):
        super().__init__()
        self.transcript = ""
        self.current_question = ""
        self.current_answer = ""
        self.user_info = {}
        self.current_feedback = None
        self.api_key = os.getenv("OPENAI_API_KEY")  # Fetch API key from environment variable
        self.ai_loading_bar = None
        self.feedback_required = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # User Info
        self.add_user_info_fields(layout)

        # URL input
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        url_layout.addWidget(QLabel("YouTube URL:"))
        url_layout.addWidget(self.url_input)
        self.load_button = QPushButton("Load Video")
        self.load_button.clicked.connect(self.load_video)
        url_layout.addWidget(self.load_button)
        layout.addLayout(url_layout)

        # Loading bar
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)  # Indeterminate progress
        self.loading_bar.hide()
        layout.addWidget(self.loading_bar)

        # Question input
        question_layout = QHBoxLayout()
        self.question_input = QLineEdit()
        question_layout.addWidget(QLabel("Question:"))
        question_layout.addWidget(self.question_input)
        self.ask_button = QPushButton("Ask")
        self.ask_button.clicked.connect(self.ask_question)
        question_layout.addWidget(self.ask_button)
        layout.addLayout(question_layout)

        # Answer display
        self.answer_display = QTextEdit()
        self.answer_display.setReadOnly(True)
        layout.addWidget(self.answer_display)

        # AI Loading bar
        self.ai_loading_bar = QProgressBar()
        self.ai_loading_bar.setRange(0, 0)  # Indeterminate progress
        self.ai_loading_bar.hide()
        layout.addWidget(self.ai_loading_bar)

        # Feedback buttons
        feedback_layout = QHBoxLayout()
        self.thumbs_up_button = QPushButton("👍 Thumbs Up")
        self.thumbs_up_button.clicked.connect(lambda: self.set_feedback("positive"))
        feedback_layout.addWidget(self.thumbs_up_button)
        self.thumbs_down_button = QPushButton("👎 Thumbs Down")
        self.thumbs_down_button.clicked.connect(lambda: self.set_feedback("negative"))
        feedback_layout.addWidget(self.thumbs_down_button)
        layout.addLayout(feedback_layout)

        # Submit feedback button
        self.submit_feedback_button = QPushButton("Submit Feedback")
        self.submit_feedback_button.clicked.connect(self.submit_feedback)
        layout.addWidget(self.submit_feedback_button)

        self.setLayout(layout)
        self.setWindowTitle('YouTube Video Q&A')
        self.setGeometry(300, 300, 600, 500)

        # Initially disable question input and ask button
        self.set_question_input_state(False)

    def add_user_info_fields(self, layout):
        user_info_layout = QVBoxLayout()

        self.nickname_input = QLineEdit()
        user_info_layout.addWidget(QLabel("Nickname:"))
        user_info_layout.addWidget(self.nickname_input)

        self.work_status_combo = QComboBox()
        self.work_status_combo.addItems(["Student", "Staff"])
        user_info_layout.addWidget(QLabel("Work Status:"))
        user_info_layout.addWidget(self.work_status_combo)

        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["Male", "Female", "Other"])
        user_info_layout.addWidget(QLabel("Gender:"))
        user_info_layout.addWidget(self.gender_combo)

        layout.addLayout(user_info_layout)

    def load_video(self):
        self.user_info = {
            "nickname": self.nickname_input.text(),
            "work_status": self.work_status_combo.currentText(),
            "gender": self.gender_combo.currentText()
        }

        if not all(self.user_info.values()):
            QMessageBox.warning(self, "Incomplete Information", "Please fill in all user information fields.")
            return

        url = self.url_input.text()
        video_id = self.extract_video_id(url)
        if video_id:
            self.loading_bar.show()
            self.load_button.setEnabled(False)
            self.loader = TranscriptLoader(video_id)
            self.loader.finished.connect(self.on_transcript_loaded)
            self.loader.start()
        else:
            self.answer_display.setText("Invalid YouTube URL.")

    def on_transcript_loaded(self, result):
        self.loading_bar.hide()
        self.load_button.setEnabled(True)
        if result.startswith("Error"):
            self.answer_display.setText(result)
        else:
            self.transcript = result
            self.answer_display.setText("Video loaded successfully. You can now ask questions.")
            self.set_question_input_state(True)

    def ask_question(self):
        if not self.transcript:
            self.answer_display.setText("Please load a video first.")
            return

        self.current_question = self.question_input.text()
        if self.current_question:
            self.answer_display.clear()
            self.ai_loading_bar.show()
            self.set_question_input_state(False)

            # Use QTimer to allow the UI to update before processing
            QTimer.singleShot(100, self.process_question)
        else:
            self.answer_display.setText("Please enter a question.")

    def process_question(self):
        self.current_answer = self.get_chatgpt_response(self.current_question, self.transcript)
        self.answer_display.setText(f"Q: {self.current_question}\n\nA: {self.current_answer}")
        self.current_feedback = None  # Reset feedback
        self.ai_loading_bar.hide()
        self.feedback_required = True
        self.update_feedback_buttons()

    def set_feedback(self, feedback):
        self.current_feedback = feedback
        self.update_feedback_buttons()

    def update_feedback_buttons(self):
        if self.current_feedback == "positive":
            self.thumbs_up_button.setStyleSheet("background-color: lightgreen;")
            self.thumbs_down_button.setStyleSheet("")
        elif self.current_feedback == "negative":
            self.thumbs_down_button.setStyleSheet("background-color: lightcoral;")
            self.thumbs_up_button.setStyleSheet("")
        else:
            self.thumbs_up_button.setStyleSheet("")
            self.thumbs_down_button.setStyleSheet("")

    def submit_feedback(self):
        if not self.current_question or not self.current_answer:
            QMessageBox.warning(self, "No Question Asked", "Please ask a question before submitting feedback.")
            return

        if self.current_feedback is None:
            QMessageBox.warning(self, "No Feedback Selected",
                                "Please select a feedback (thumbs up or down) before submitting.")
            return

        self.log_to_csv(self.current_feedback)
        self.reset_after_submission()
        QMessageBox.information(self, "Feedback Submitted", "Thank you for your feedback!")

    def reset_after_submission(self):
        self.current_question = ""
        self.current_answer = ""
        self.current_feedback = None
        self.question_input.clear()
        self.answer_display.clear()
        self.update_feedback_buttons()
        self.feedback_required = False
        self.set_question_input_state(True)

    def set_question_input_state(self, enabled):
        self.question_input.setEnabled(enabled)
        self.ask_button.setEnabled(enabled)
        palette = self.question_input.palette()
        if enabled:
            palette.setColor(QPalette.Base, Qt.white)
        else:
            palette.setColor(QPalette.Base, Qt.lightGray)
        self.question_input.setPalette(palette)

    def log_to_csv(self, feedback):
        filename = "/app/data/qa_feedback_log.csv"
        fieldnames = ["timestamp", "nickname", "work_status", "gender", "question", "answer", "feedback"]

        file_exists = os.path.isfile(filename)

        with open(filename, 'a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            writer.writerow({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "nickname": self.user_info["nickname"],
                "work_status": self.user_info["work_status"],
                "gender": self.user_info["gender"],
                "question": self.current_question,
                "answer": self.current_answer,
                "feedback": feedback
            })

    @staticmethod
    def extract_video_id(url):
        video_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
        return video_id_match.group(1) if video_id_match else None

    def get_chatgpt_response(self, question, context):
        if not self.api_key:
            return "API key is not set. Please set the OPENAI_API_KEY environment variable to use this feature."

        client = OpenAI(api_key=self.api_key)

        try:
            response = client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an AI assistant that only answers questions based on the provided YouTube video transcript. You must not use any external knowledge or information not present in the transcript. If the question cannot be answered using only the information in the transcript, respond with 'This information is not provided in the video transcript.'"
                    },
                    {
                        "role": "user",
                        "content": f"Here's the transcript from a YouTube video:\n\n{context}\n\nBased solely on this transcript, please answer the following question. Remember, only use information from the transcript. If the information isn't in the transcript, say so:\n\n{question}"
                    },
                ],
                max_tokens=150  # Adjust as needed
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            error_message = str(e)
            if "401" in error_message:
                self.api_key = ""  # Clear the invalid API key
                return "Authentication failed. Please check your API key and try again."
            else:
                print(f"Error in API response: {error_message}")
                return f"Sorry, I couldn't generate an answer. Error: {error_message}"

    def process_question_headless(self, youtube_url, question):
        video_id = self.extract_video_id(youtube_url)
        if not video_id:
            return {"error": "Invalid YouTube URL"}

        # Load transcript
        loader = TranscriptLoader(video_id)
        transcript = loader.run()

        if isinstance(transcript, str) and transcript.startswith("Error"):
            return {"error": transcript}

        # Process question
        answer = self.get_chatgpt_response(question, transcript)

        # Log the interaction
        self.log_to_csv_headless(youtube_url, question, answer)

        return {
            "question": question,
            "answer": answer
        }

    def log_to_csv_headless(self, youtube_url, question, answer):
        filename = "/app/data/qa_feedback_log.csv"
        fieldnames = ["timestamp", "youtube_url", "question", "answer"]

        file_exists = os.path.isfile(filename)

        with open(filename, 'a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            writer.writerow({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "youtube_url": youtube_url,
                "question": question,
                "answer": answer
            })


def main():
    app = QApplication(sys.argv)
    ex = YouTubeQAApp()
    ex.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
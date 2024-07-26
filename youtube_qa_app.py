import os
import re
import csv
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI


class YouTubeQAApp:
    def __init__(self):
        self.transcript = ""
        self.current_question = ""
        self.current_answer = ""
        self.user_info = {}
        self.current_feedback = None
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)

    @staticmethod
    def extract_video_id(url):
        video_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
        return video_id_match.group(1) if video_id_match else None

    def get_transcript(self, video_id):
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            return " ".join([entry['text'] for entry in transcript])
        except Exception as e:
            return f"Error: {str(e)}"

    def get_chatgpt_response(self, question, context):
        if not self.api_key:
            return "API key is not set. Please set the OPENAI_API_KEY environment variable to use this feature."

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
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
                max_tokens=150
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            error_message = str(e)
            if "401" in error_message:
                return "Authentication failed. Please check your API key and try again."
            else:
                print(f"Error in API response: {error_message}")
                return f"Sorry, I couldn't generate an answer. Error: {error_message}"

    def log_to_csv(self, feedback=None):
        filename = "qa_feedback_log.csv"
        fieldnames = ["timestamp", "nickname", "work_status", "gender", "question", "answer", "feedback"]

        file_exists = os.path.isfile(filename)

        with open(filename, 'a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            writer.writerow({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "nickname": self.user_info.get("nickname", "N/A"),
                "work_status": self.user_info.get("work_status", "N/A"),
                "gender": self.user_info.get("gender", "N/A"),
                "question": self.current_question,
                "answer": self.current_answer,
                "feedback": feedback or "N/A"
            })

    def process_question_headless(self, youtube_url, question, user_info=None):
        self.user_info = user_info or {}
        video_id = self.extract_video_id(youtube_url)
        if not video_id:
            return {"error": "Invalid YouTube URL"}

        self.transcript = self.get_transcript(video_id)
        if self.transcript.startswith("Error"):
            return {"error": self.transcript}

        self.current_question = question
        self.current_answer = self.get_chatgpt_response(question, self.transcript)

        # Log the interaction without feedback initially
        self.log_to_csv()

        return {
            "question": self.current_question,
            "answer": self.current_answer
        }

    def submit_feedback(self, feedback):
        if not self.current_question or not self.current_answer:
            return {"error": "No question has been asked yet"}

        self.current_feedback = feedback
        self.log_to_csv(feedback)

        return {"message": "Feedback submitted successfully"}


# This part is optional, you can remove it if you're not running this file directly
if __name__ == "__main__":
    print("This module is designed to be imported and used by other scripts.")
    print("It contains the YouTubeQAApp class for processing YouTube video transcripts and answering questions.")
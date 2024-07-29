import csv
import os
import re
from datetime import datetime

from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi


class YouTubeQAApp:
    def __init__(self):
        self.transcript = ""
        self.current_question = ""
        self.current_answer = ""
        self.user_info = {}
        self.current_feedback = None
        self.current_video_url = ""
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.feedback_provided = True  # Initialize as True to allow the first question
        self.last_question_unrelated = False

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
                        "content": "You are an AI assistant that answers questions based on the provided YouTube video transcript. While you should prioritize information from the transcript, you can also provide general explanations for concepts mentioned in the video, even if they're not explicitly defined. If a question is completely unrelated to the video content, politely redirect the user to ask about topics covered in the video."
                    },
                    {
                        "role": "user",
                        "content": f"Here's the transcript from a YouTube video:\n\n{context}\n\nPlease answer the following question, primarily using information from the transcript. If the concept is mentioned but not fully explained, you can provide a brief general explanation:\n\n{question}"
                    },
                ],
                max_tokens=200
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
        fieldnames = ["timestamp", "participant_id", "work_status", "gender", "video_url", "question", "answer", "feedback"]

        file_exists = os.path.isfile(filename)

        with open(filename, 'a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            writer.writerow({
                "timestamp": datetime.now().strftime("%Y-%m-d %H:%M:%S"),
                "participant_id": self.user_info.get("participant_id", "N/A"),
                "work_status": self.user_info.get("work_status", "N/A"),
                "gender": self.user_info.get("gender", "N/A"),
                "video_url": self.current_video_url,
                "question": self.current_question,
                "answer": self.current_answer,
                "feedback": feedback or "N/A"
            })

    def process_question_stream(self, youtube_url, question, user_info=None):
        if not self.feedback_provided and not self.last_question_unrelated:
            yield "Please provide feedback for the previous question before asking a new one."
            return

        self.user_info = user_info or {}
        self.current_video_url = youtube_url
        video_id = self.extract_video_id(youtube_url)
        if not video_id:
            yield "Error: Invalid YouTube URL"
            return

        self.transcript = self.get_transcript(video_id)
        if self.transcript.startswith("Error"):
            yield self.transcript
            return

        self.current_question = question
        self.current_answer = ""
        for chunk in self.get_chatgpt_response_stream(question, self.transcript):
            self.current_answer += chunk
            yield chunk

        # Check if the answer indicates the question is unrelated to the video
        if "This information is not provided in the video transcript" in self.current_answer:
            self.log_to_csv(feedback="N/A")
            self.last_question_unrelated = True
        else:
            self.last_question_unrelated = False

        self.feedback_provided = False

    def get_chatgpt_response_stream(self, question, context):
        if not self.api_key:
            yield "API key is not set. Please set the OPENAI_API_KEY environment variable to use this feature."
            return

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an AI assistant that answers questions based on the provided YouTube video transcript. While you should prioritize information from the transcript, you can also provide general explanations for concepts mentioned in the video, even if they're not explicitly defined. If a question is completely unrelated to the video content, politely redirect the user to ask about topics covered in the video."
                    },
                    {
                        "role": "user",
                        "content": f"Here's the transcript from a YouTube video:\n\n{context}\n\nPlease answer the following question, primarily using information from the transcript. If the concept is mentioned but not fully explained, you can provide a brief general explanation:\n\n{question}"
                    },
                ],
                max_tokens=2000,
                stream=True
            )
            for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            error_message = str(e)
            if "401" in error_message:
                yield "Authentication failed. Please check your API key and try again."
            else:
                print(f"Error in API response: {error_message}")
                yield f"Sorry, I couldn't generate an answer. Error: {error_message}"

    def submit_feedback(self, feedback):
        if not self.current_question or not self.current_answer:
            return {"error": "No question has been asked yet"}

        self.current_feedback = feedback
        self.log_to_csv(feedback)
        self.feedback_provided = True

        return {"message": "Feedback submitted successfully"}

    def create_new_csv(self):
        filename = "qa_feedback_log.csv"
        fieldnames = ["timestamp", "participant_id", "work_status", "gender", "video_url", "question", "answer", "feedback"]

        with open(filename, 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()


# This part is optional, you can remove it if you're not running this file directly
if __name__ == "__main__":
    print("This module is designed to be imported and used by other scripts.")
    print("It contains the YouTubeQAApp class for processing YouTube video transcripts and answering questions.")
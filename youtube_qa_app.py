import csv
import logging
import os
import re
import sys
from datetime import datetime

from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class YouTubeQAApp:
    def __init__(self):
        logger.info("Initializing YouTubeQAApp")
        self.transcript = ""
        self.current_question = ""
        self.current_answer = ""
        self.user_info = {}
        self.current_feedback = None
        self.current_video_url = ""
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OpenAI API key not set")
        self.client = OpenAI(api_key=self.api_key)
        self.feedback_provided = True  # Initialize as True to allow the first question
        self.last_question_unrelated = False
        logger.info("YouTubeQAApp initialized successfully")

    @staticmethod
    def extract_video_id(url):
        logger.info(f"Extracting video ID from URL: {url}")
        video_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
        if video_id_match:
            video_id = video_id_match.group(1)
            logger.info(f"Video ID extracted: {video_id}")
            return video_id
        else:
            logger.warning(f"Could not extract video ID from URL: {url}")
            return None

    def get_transcript(self, video_id):
        logger.info(f"Fetching transcript for video ID: {video_id}")
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            logger.info(f"Transcript fetched successfully for video ID: {video_id}")
            return " ".join([entry['text'] for entry in transcript])
        except Exception as e:
            logger.error(f"Error fetching transcript for video ID {video_id}: {str(e)}")
            return f"Error: {str(e)}"

    def get_chatgpt_response(self, question, context):
        logger.info("Generating ChatGPT response")
        if not self.api_key:
            logger.error("API key is not set")
            return "API key is not set. Please set the OPENAI_API_KEY environment variable to use this feature."

        try:
            logger.info("Sending request to OpenAI API")
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
            logger.info("Received response from OpenAI API")
            return response.choices[0].message.content.strip()
        except Exception as e:
            error_message = str(e)
            if "401" in error_message:
                logger.error(f"Authentication failed: {error_message}")
                return "Authentication failed. Please check your API key and try again."
            else:
                logger.error(f"Error in API response: {error_message}")
                return f"Sorry, I couldn't generate an answer. Error: {error_message}"

    def log_to_csv(self, feedback=None):
        logger.info("Logging interaction to CSV")
        filename = "qa_feedback_log.csv"
        fieldnames = ["timestamp", "participant_id", "work_status", "gender", "video_url", "question", "answer",
                      "feedback"]

        file_exists = os.path.isfile(filename)

        try:
            with open(filename, 'a', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)

                if not file_exists:
                    logger.info("Creating new CSV file with headers")
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
            logger.info("Interaction logged successfully to CSV")
        except Exception as e:
            logger.error(f"Error logging to CSV: {str(e)}")

    def process_question_stream(self, youtube_url, question, user_info=None):
        logger.info(f"Processing question: {question}")
        if not self.feedback_provided and not self.last_question_unrelated:
            logger.warning("Feedback not provided for previous question")
            yield "Please provide feedback for the previous question before asking a new one."
            return

        self.user_info = user_info or {}
        self.current_video_url = youtube_url
        video_id = self.extract_video_id(youtube_url)
        if not video_id:
            logger.error(f"Invalid YouTube URL: {youtube_url}")
            yield "Error: Invalid YouTube URL"
            return

        self.transcript = self.get_transcript(video_id)
        if self.transcript.startswith("Error"):
            logger.error(f"Error getting transcript: {self.transcript}")
            yield self.transcript
            return

        self.current_question = question
        self.current_answer = ""
        logger.info("Streaming ChatGPT response")
        for chunk in self.get_chatgpt_response_stream(question, self.transcript):
            self.current_answer += chunk
            yield chunk

        # Check if the answer indicates the question is unrelated to the video
        if "This information is not provided in the video transcript" in self.current_answer:
            logger.info("Question unrelated to video content")
            self.log_to_csv(feedback="N/A")
            self.last_question_unrelated = True
        else:
            self.last_question_unrelated = False

        self.feedback_provided = False
        logger.info("Question processing completed")

    def get_chatgpt_response_stream(self, question, context):
        logger.info("Generating streaming ChatGPT response")

        if not self.api_key:
            logger.error("API key is not set")
            yield "API key is not set. Please set the OPENAI_API_KEY environment variable to use this feature."
            return

        try:
            logger.info("Sending streaming request to OpenAI API")
            logger.info(f"Using model: gpt-4o-mini")
            logger.info(f"Max tokens: 2000")
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
            logger.info("Completed streaming response from OpenAI API")
        except Exception as e:
            error_message = str(e)
            if "401" in error_message:
                logger.error(f"Authentication failed: {error_message}")
                yield "Authentication failed. Please check your API key and try again."
            else:
                logger.error(f"Error in API response: {error_message}")
                yield f"Sorry, I couldn't generate an answer. Error: {error_message}"

    def submit_feedback(self, feedback):
        logger.info(f"Submitting feedback: {feedback}")
        if not self.current_question or not self.current_answer:
            logger.warning("Attempt to submit feedback without a question")
            return {"error": "No question has been asked yet"}

        self.current_feedback = feedback
        self.log_to_csv(feedback)
        self.feedback_provided = True
        logger.info("Feedback submitted successfully")
        return {"message": "Feedback submitted successfully"}

    def create_new_csv(self):
        logger.info("Creating new CSV file")
        filename = "qa_feedback_log.csv"
        fieldnames = ["timestamp", "participant_id", "work_status", "gender", "video_url", "question", "answer",
                      "feedback"]

        try:
            with open(filename, 'w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
            logger.info("New CSV file created successfully")
        except Exception as e:
            logger.error(f"Error creating new CSV file: {str(e)}")


# This part is optional, you can remove it if you're not running this file directly
if __name__ == "__main__":
    logger.info("youtube_qa_app.py executed directly")
    print("This module is designed to be imported and used by other scripts.")
    print("It contains the YouTubeQAApp class for processing YouTube video transcripts and answering questions.")

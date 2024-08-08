import csv
import logging
import os
import re
import sys
import json
import hashlib
from datetime import datetime

from openai import OpenAI
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from ratelimit import limits, sleep_and_retry

# Configure logging to print to console
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
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        if not self.openai_api_key:
            logger.warning("OpenAI API key not set")
        if not self.youtube_api_key:
            logger.warning("YouTube API key not set")
        self.client = OpenAI(api_key=self.openai_api_key)
        self.youtube = build('youtube', 'v3', developerKey=self.youtube_api_key)
        self.feedback_provided = True
        self.last_question_unrelated = False
        self.cache_dir = "transcript_cache"
        os.makedirs(self.cache_dir, exist_ok=True)
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

    def get_cache_filename(self, video_id):
        return os.path.join(self.cache_dir, f"{video_id}.json")

    def get_transcript_from_cache(self, video_id):
        cache_file = self.get_cache_filename(video_id)
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
            logger.info(f"Transcript loaded from cache for video ID: {video_id}")
            return cached_data['transcript']
        return None

    def save_transcript_to_cache(self, video_id, transcript):
        cache_file = self.get_cache_filename(video_id)
        with open(cache_file, 'w') as f:
            json.dump({'video_id': video_id, 'transcript': transcript}, f)
        logger.info(f"Transcript saved to cache for video ID: {video_id}")

    @sleep_and_retry
    @limits(calls=1, period=5)  # Adjust as needed based on API limits
    def get_transcript(self, video_url):
        logger.info(f"Fetching transcript for video URL: {video_url}")
        video_id = self.extract_video_id(video_url)
        if not video_id:
            return "Error: Invalid YouTube URL"

        cached_transcript = self.get_transcript_from_cache(video_id)
        if cached_transcript:
            return cached_transcript

        try:
            captions = self.youtube.captions().list(
                part='snippet',
                videoId=video_id
            ).execute()

            if not captions.get('items'):
                return "Error: No captions found for this video"

            caption_id = captions['items'][0]['id']
            subtitle = self.youtube.captions().download(
                id=caption_id,
                tfmt='srt'
            ).execute()

            transcript = self.srt_to_plain_text(subtitle.decode('utf-8'))
            self.save_transcript_to_cache(video_id, transcript)
            return transcript

        except HttpError as e:
            logger.error(f"HTTP error occurred: {e}")
            return f"Error: {e}"
        except Exception as e:
            logger.error(f"Error fetching transcript for video ID {video_id}: {str(e)}")
            return f"Error: Unable to fetch transcript. {str(e)}"

    def srt_to_plain_text(self, srt_string):
        lines = srt_string.strip().split('\n')
        return ' '.join(line for line in lines if not line.isdigit() and '-->' not in line).replace('\r', '')

    def get_chatgpt_response(self, question, context):
        logger.info("Generating ChatGPT response")
        if not self.openai_api_key:
            logger.error("OpenAI API key is not set")
            return "API key is not set. Please set the OPENAI_API_KEY environment variable to use this feature."

        try:
            logger.info("Sending request to OpenAI API")
            logger.info(f"Using model: gpt-4o-mini")
            logger.info(f"Max tokens: 200")
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
            logger.error(f"Full error details: {repr(e)}")
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
        self.current_question = question
        self.current_answer = ""

        self.transcript = self.get_transcript(youtube_url)
        if self.transcript.startswith("Error"):
            logger.error(f"Error getting transcript: {self.transcript}")
            yield self.transcript
            return

        logger.info("Streaming ChatGPT response")
        response = self.get_chatgpt_response(question, self.transcript)
        self.current_answer = response
        yield response

        # Check if the answer indicates the question is unrelated to the video
        if "This information is not provided in the video transcript" in self.current_answer:
            logger.info("Question unrelated to video content")
            self.log_to_csv(feedback="N/A")
            self.last_question_unrelated = True
        else:
            self.last_question_unrelated = False

        self.feedback_provided = False
        logger.info("Question processing completed")

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

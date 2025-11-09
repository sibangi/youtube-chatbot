import csv
import json
import logging
import os
import re
import sys
import time
from datetime import datetime

import assemblyai as aai
import yt_dlp
from openai import OpenAI
from ratelimit import limits, sleep_and_retry
import base64
import tempfile

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
        self.assemblyai_api_key = os.getenv("ASSEMBLYAI_API_KEY")
        if not self.openai_api_key:
            logger.warning("OpenAI API key not set")
        if not self.assemblyai_api_key:
            logger.warning("AssemblyAI API key not set")
        self.client = OpenAI(api_key=self.openai_api_key)
        aai.settings.api_key = self.assemblyai_api_key
        self.transcriber = aai.Transcriber()
        self.feedback_provided = True
        self.last_question_unrelated = False
        self.cache_dir = "transcript_cache"
        self.download_dir = "audio_downloads"
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.download_dir, exist_ok=True)

        # Environment and cookies configuration
        self.is_server = bool(os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID") or os.getenv("RENDER_EXTERNAL_URL"))
        self.enable_browser_cookies = os.getenv("ENABLE_BROWSER_COOKIES", "0").lower() in ("1", "true", "yes")
        self.offline_mode = os.getenv("OFFLINE_MODE", "0").lower() in ("1", "true", "yes")
        self.cookies_file = None
        self._prepare_cookies()
        logger.info("YouTubeQAApp initialized successfully")

    def _prepare_cookies(self):
        """
        Prepare a cookies file for yt-dlp based on environment variables.
        Supported env vars:
          - YTDLP_COOKIES_FILE: path to a Netscape cookie file
          - YTDLP_COOKIES: raw Netscape cookie content (string)
          - YTDLP_COOKIES_B64: base64-encoded Netscape cookie content
        """
        try:
            cookies_path = os.getenv("YTDLP_COOKIES_FILE")
            cookies_raw = os.getenv("YTDLP_COOKIES")
            cookies_b64 = os.getenv("YTDLP_COOKIES_B64")

            # Prefer existing file path if valid
            if cookies_path and os.path.isfile(cookies_path):
                self.cookies_file = cookies_path
                logger.info(f"Using cookies file from YTDLP_COOKIES_FILE: {self.cookies_file}")
                return

            # If raw or b64 provided, write to a persistent file if possible
            content = None
            if cookies_b64:
                try:
                    content = base64.b64decode(cookies_b64).decode("utf-8")
                except Exception as e:
                    logger.warning(f"Failed to decode YTDLP_COOKIES_B64: {e}")
            elif cookies_raw:
                content = cookies_raw

            if content:
                # Prefer Render persistent disk if available
                base_dir = "/app/data" if os.path.isdir("/app/data") else self.download_dir
                os.makedirs(base_dir, exist_ok=True)
                dest = os.path.join(base_dir, "cookies.txt")
                with open(dest, "w") as f:
                    f.write(content)
                self.cookies_file = dest
                logger.info(f"Wrote cookies to: {self.cookies_file}")
                return

            # No cookies available
            self.cookies_file = None
            logger.info("No yt-dlp cookies provided via environment.")
        except Exception as e:
            logger.warning(f"Cookie preparation failed: {e}")
            self.cookies_file = None

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

    def download_progress_hook(self, d):
        if d['status'] == 'downloading':
            progress = int(float(d['_percent_str'].strip('%')))
            yield ('download', progress)
        elif d['status'] == 'finished':
            yield ('download', 100)

    def download_audio(self, video_url):
        logger.info(f"Downloading audio from video: {video_url}")
        video_id = self.extract_video_id(video_url)
        if not video_id:
            return "Error: Invalid YouTube URL"

        output_template = os.path.join(self.download_dir, f"{video_id}.%(ext)s")

        base_opts = {
            'format': 'm4a/bestaudio/best',
            'outtmpl': output_template,
            'progress_hooks': [self.download_progress_hook],
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9'
            }
        }

        # 1) Prefer an explicit cookie file provided via env
        if self.cookies_file:
            ydl_opts = {**base_opts, 'cookiefile': self.cookies_file}
            try:
                logger.info(f"Attempting download with cookiefile: {self.cookies_file}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=True)
                    filename = ydl.prepare_filename(info)
                logger.info(f"Audio downloaded successfully with cookiefile: {filename}")
                return filename
            except Exception as e:
                logger.warning(f"Failed with cookiefile: {e}")
                # continue to next strategy

        # 2) Optionally try reading cookies from a local browser (off by default, problematic on servers)
        try_browsers = self.enable_browser_cookies and (not self.is_server or self.enable_browser_cookies)
        if try_browsers:
            browsers = ['chrome', 'firefox', 'safari', 'edge']
            for browser in browsers:
                ydl_opts = {**base_opts, 'cookiesfrombrowser': (browser,)}
                try:
                    logger.info(f"Attempting download with {browser} cookies...")
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(video_url, download=True)
                        filename = ydl.prepare_filename(info)
                    logger.info(f"Audio downloaded successfully using {browser} cookies: {filename}")
                    return filename
                except Exception as e:
                    logger.warning(f"Failed with {browser} cookies: {str(e)}")

        # 3) Last resort: try without cookies with additional extractor args
        logger.info("Trying download without cookies but with additional options...")
        ydl_opts = {
            **base_opts,
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                filename = ydl.prepare_filename(info)
            logger.info(f"Audio downloaded successfully without cookies: {filename}")
            return filename
        except Exception as e:
            logger.error(
                "Error downloading audio from video %s: %s. If this is a members-only/private or rate-limited video, "
                "you may need to provide YouTube cookies. See README for YTDLP_COOKIES* env vars.",
                video_id, str(e)
            )
            return None

    def simulate_transcribe_progress(self):
        for i in range(1, 101):
            yield ('transcribe', i)
            time.sleep(0.1)  # Adjust this value to control the speed of the simulated progress

    def process_video(self, video_url):
        logger.info(f"Processing video: {video_url}")
        self.current_video_url = video_url
        video_id = self.extract_video_id(video_url)

        cached_transcript = self.get_transcript_from_cache(video_id)
        if cached_transcript:
            logger.info(f"Using cached transcript for video ID: {video_id}")
            self.transcript = cached_transcript
            yield ('download', 100)
            yield ('transcribe', 100)
            yield "done"
            return

        # If offline mode is enabled, do not attempt to download; require cache
        if self.offline_mode:
            logger.info("Offline mode enabled and transcript not in cache; skipping download.")
            yield "Error: Offline mode is enabled and this video is not pre-cached."
            return

        audio_file = self.download_audio(video_url)
        if not audio_file:
            yield "Error: Failed to download audio from video"
            return

        yield ('download', 100)

        try:
            # Simulate transcription progress
            for progress in self.simulate_transcribe_progress():
                yield progress

            # Actual transcription
            transcript = self.transcriber.transcribe(audio_file)
            if transcript.status == 'completed':
                self.transcript = transcript.text
                self.save_transcript_to_cache(video_id, self.transcript)
                logger.info(f"Transcript fetched and cached successfully for video URL: {video_url}")
                yield ('transcribe', 100)
                yield "done"
            else:
                logger.error(f"Transcription failed with status: {transcript.status}")
                yield "Error: Transcription failed"
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            yield f"Error: Transcription failed. {str(e)}"

    @sleep_and_retry
    @limits(calls=1, period=5)  # Adjust as needed based on API limits
    def get_chatgpt_response(self, question, context):
        logger.info("Generating ChatGPT response")
        if not self.openai_api_key:
            logger.error("OpenAI API key is not set")
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
                stream=True
            )
            return response
        except Exception as e:
            error_message = str(e)
            logger.error(f"Full error details: {repr(e)}")
            return f"Sorry, I couldn't generate an answer. Error: {error_message}"

    def process_question_stream(self, youtube_url, question, user_info=None):
        logger.info(f"Processing question: {question}")
        if not self.transcript:
            yield "Please load a video first before asking questions."
            return

        self.user_info = user_info or {}
        self.current_question = question
        self.current_answer = ""

        response = self.get_chatgpt_response(question, self.transcript)
        if isinstance(response, str):  # Error occurred
            yield response
            return

        for chunk in response:
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                self.current_answer += content
                yield content

    def submit_feedback(self, feedback):
        logger.info(f"Submitting feedback: {feedback}")
        if not self.current_question or not self.current_answer:
            logger.warning("Attempt to submit feedback without a question")
            return {"error": "No question has been asked yet"}

        self.current_feedback = feedback
        self.log_to_csv(feedback)
        logger.info("Feedback submitted successfully")
        return {"message": "Feedback submitted successfully"}

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
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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


if __name__ == "__main__":
    logger.info("youtube_qa_app.py executed directly")
    print("This module is designed to be imported and used by other scripts.")
    print("It contains the YouTubeQAApp class for processing YouTube video transcripts and answering questions.")

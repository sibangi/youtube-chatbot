# YouTube Chatbot

A Flask-based web application that transcribes YouTube videos and allows users to ask questions about the content using AI.

## Features

- 🎥 Download and transcribe YouTube videos
- 🤖 AI-powered Q&A using OpenAI GPT
- 💾 Transcript caching for faster repeated access
- 🔐 Authentication system
- 📊 Admin panel with feedback logging
- 📝 CSV export of Q&A interactions

## Prerequisites

- Python 3.11 or higher
- OpenAI API key
- AssemblyAI API key

## Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd youtube-chatbot-2
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv

   # On Windows
   venv\Scripts\activate

   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**

   Copy `.env.example` to `.env` and fill in your API keys:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your actual values:
   ```
   OPENAI_API_KEY=sk-...
   ASSEMBLYAI_API_KEY=...
   AUTH_USERNAME=admin
   AUTH_PASSWORD=your_password
   ```

## Running Locally

### Development Mode

## YouTube Download Authentication (yt-dlp cookies)
Many YouTube videos now require authentication or trigger bot checks that block unauthenticated downloads. On local machines, yt-dlp can sometimes read cookies directly from your browser, but that does not work on server environments like Render.

This app supports providing YouTube cookies to yt-dlp via environment variables so downloads work reliably in production.

Supported environment variables (only one is needed):
- YTDLP_COOKIES_FILE: Absolute path to a Netscape-format cookies file
- YTDLP_COOKIES: The full Netscape cookie file content as a string
- YTDLP_COOKIES_B64: Base64-encoded Netscape cookie file content (recommended for Render)

Optional toggle:
- ENABLE_BROWSER_COOKIES: Set to "1" to allow attempting cookies-from-browser locally. Default is off to avoid errors on servers.

How to export cookies:
1) Install the "Get cookies.txt" browser extension (or any tool that exports in Netscape format).
2) While logged in to YouTube in your browser, export cookies for youtube.com and google.com as a single cookies.txt file.
3) Verify the file begins with lines like:
```
# Netscape HTTP Cookie File
.youtube.com	TRUE	/	FALSE	...
```

Using cookies locally:
- Point the app to the file path:
```
YTDLP_COOKIES_FILE=/absolute/path/to/cookies.txt
```
Or paste the content directly:
```
YTDLP_COOKIES="<paste Netscape cookies content here>"
```

Using cookies on Render (recommended: base64):
- Base64-encode your cookies file locally:
```
base64 -i cookies.txt | pbcopy   # macOS
# or
base64 -w0 cookies.txt | xclip -selection clipboard   # Linux
```
- In Render dashboard, add an env var `YTDLP_COOKIES_B64` and paste the encoded value.

Notes:
- The app will first try the provided cookie file. If none is provided, it falls back to unauthenticated download with extra options, which may fail for members-only/private or rate-limited videos.
- Browser cookie auto-detection is disabled by default on servers to prevent noisy errors like "could not find chrome cookies database".

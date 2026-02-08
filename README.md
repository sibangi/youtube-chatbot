# YouTube Q&A Chatbot

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Web_App-000000?style=flat&logo=flask&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?style=flat&logo=openai&logoColor=white)
![Render](https://img.shields.io/badge/Deployed_on-Render-46E3B7?style=flat&logo=render&logoColor=white)

An AI-powered web application that transcribes YouTube videos and lets users ask questions about the content in real time. Built as a teaching tool for higher education — students load a lecture or tutorial video and interact with it through natural-language Q&A.

Deployed in production and actively used by undergraduate students as part of a BSc dissertation project at the University of Nottingham.

## Features

| Feature | Description |
|---------|-------------|
| Video transcription | Downloads and transcribes YouTube videos via AssemblyAI |
| AI-powered Q&A | Answers questions about video content using OpenAI GPT-4o-mini |
| Streaming responses | Real-time answer generation via Server-Sent Events (SSE) |
| Transcript caching | Avoids redundant API calls for previously transcribed videos |
| Authentication | Session-based login to control student access |
| Admin panel | View all Q&A interactions, export to CSV for analysis |
| Rate limiting | Prevents API abuse in shared classroom environments |
| Offline mode | Development mode using cached transcripts (no API calls) |

## Architecture

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│  Browser  │────▶│  Flask App   │────▶│  OpenAI API  │
│  (HTML)   │◀────│  (app.py)    │     │  GPT-4o-mini │
└──────────┘ SSE └──────┬───────┘     └──────────────┘
                        │
              ┌─────────┴─────────┐
              │                   │
     ┌──────────────┐    ┌──────────────┐
     │  yt-dlp      │    │ AssemblyAI   │
     │  (download)  │    │ (transcribe) │
     └──────────────┘    └──────────────┘
```

## Repository Structure

```
youtube-chatbot/
├── app.py               # Flask routes, auth, SSE streaming
├── youtube_qa_app.py    # Core engine: download, transcribe, Q&A
├── run_local.py         # Local development runner
├── templates/
│   ├── index.html       # Main Q&A interface
│   ├── login.html       # Authentication page
│   └── admin.html       # Admin panel (interaction logs)
├── render.yaml          # Render deployment configuration
├── requirements.txt     # Python dependencies
├── runtime.txt          # Python version (Render)
└── .env.example         # Environment variable template
```

## Quick Start

```bash
git clone https://github.com/sibangi/youtube-chatbot.git
cd youtube-chatbot
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # Add your API keys
python run_local.py
```

Requires API keys for [OpenAI](https://platform.openai.com/) and [AssemblyAI](https://www.assemblyai.com/).

## Deployment

The app is configured for [Render](https://render.com/) via `render.yaml`. Key environment variables:

| Variable | Purpose |
|----------|--------|
| `OPENAI_API_KEY` | OpenAI API authentication |
| `ASSEMBLYAI_API_KEY` | AssemblyAI transcription service |
| `AUTH_USERNAME` / `AUTH_PASSWORD` | Student login credentials |
| `YTDLP_COOKIES_B64` | Base64-encoded YouTube cookies (see below) |

<details>
<summary><strong>YouTube cookie configuration (yt-dlp)</strong></summary>

<br>

YouTube may block unauthenticated downloads on server environments. The app supports three methods for providing cookies to yt-dlp:

- `YTDLP_COOKIES_FILE` — path to a Netscape-format cookies file
- `YTDLP_COOKIES` — cookie file content as a string
- `YTDLP_COOKIES_B64` — base64-encoded cookie file (recommended for Render)

To export cookies: install a "Get cookies.txt" browser extension, export cookies for youtube.com while logged in, then base64-encode:

```bash
base64 -i cookies.txt | pbcopy   # macOS
```

</details>

## Dependencies

- [Flask](https://flask.palletsprojects.com/) — web framework
- [OpenAI Python SDK](https://github.com/openai/openai-python) — GPT-4o-mini integration
- [AssemblyAI](https://www.assemblyai.com/) — speech-to-text transcription
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — YouTube video download
- [Gunicorn](https://gunicorn.org/) — production WSGI server

## License

[MIT](LICENSE)

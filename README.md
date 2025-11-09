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

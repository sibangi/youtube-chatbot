#!/usr/bin/env python
"""
Local development runner for YouTube Chatbot
This script loads environment variables and runs the Flask app in debug mode
"""

import os
import warnings
from dotenv import load_dotenv

# Suppress urllib3 OpenSSL warning on macOS
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL 1.1.1+')

# Load environment variables from .env file
load_dotenv()

# Check for required environment variables
required_vars = ['OPENAI_API_KEY', 'ASSEMBLYAI_API_KEY', 'AUTH_USERNAME', 'AUTH_PASSWORD']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print("❌ Error: Missing required environment variables:")
    for var in missing_vars:
        print(f"   - {var}")
    print("\n📝 Please create a .env file with these variables.")
    print("   You can copy .env.example and fill in your values:")
    print("   cp .env.example .env")
    exit(1)

print("✅ All environment variables loaded successfully!")
print("🚀 Starting Flask development server...")
print("📍 Application will be available at: http://localhost:5000")
print("🔐 Login with credentials from your .env file")
print("\n Press Ctrl+C to stop the server\n")

# Import and run the app
from app import app

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

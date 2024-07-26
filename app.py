# File: app.py
# import sys
import warnings

from PyQt5.QtWidgets import QApplication
from urllib3.exceptions import NotOpenSSLWarning

from youtube_qa_app import YouTubeQAApp

warnings.filterwarnings("ignore", category=NotOpenSSLWarning)


def create_app():
    # Create the QApplication instance
    qt_app = QApplication(sys.argv)

    # Create the YouTubeQAApp instance
    ex = YouTubeQAApp()

    return qt_app, ex


def main():
    # Create both the QApplication and YouTubeQAApp instances
    qt_app, youtube_qa_app = create_app()

    # Show the main window
    youtube_qa_app.show()

    # Start the event loop
    sys.exit(qt_app.exec_())


if __name__ == '__main__':
    main()

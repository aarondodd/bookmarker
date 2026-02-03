"""Entry point for Bookmarker."""

import sys

from PyQt6.QtWidgets import QApplication

from bookmarker.app import BookmarkerApp
from bookmarker.utils.config import create_default_config


def main():
    create_default_config()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    window = BookmarkerApp()
    window.hide()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

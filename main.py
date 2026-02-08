"""Entry point for Bookmarker."""

import os
import sys

# On Linux, Qt6's D-Bus StatusNotifierItem (SNI) tray backend is incompatible
# with several desktop environments (MATE indicator-applet, some XFCE panels).
# Force the XEmbed protocol which renders icons locally and works reliably.
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_SYSTRAY_NO_DBUS", "1")

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

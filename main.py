"""Entry point for Bookmarker."""

import sys


def _run_native_host() -> int:
    """Browser-sync bridge: act as the Chrome native-messaging host relaying
    length-prefixed JSON between the extension's stdio and the running app's
    loopback bridge. Chrome spawns this via the native-host manifest, which
    points at this executable with --native-host. Must run before QApplication
    so a Chrome-spawned host never boots the GUI.
    """
    from bookmarker.automation.native_host import run
    from bookmarker.automation.installer import EXTENSION_ID
    from bookmarker.utils.config import bridge_handshake_path

    return run(bridge_handshake_path(), extension_id=EXTENSION_ID)


def main():
    if "--native-host" in sys.argv[1:]:
        sys.exit(_run_native_host())

    from PyQt6.QtWidgets import QApplication

    from bookmarker.app import BookmarkerApp
    from bookmarker.utils.config import create_default_config

    create_default_config()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    window = BookmarkerApp()
    window.hide()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

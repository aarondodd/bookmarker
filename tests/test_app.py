"""Tests for main application."""

import sys
import pytest
from unittest.mock import patch, MagicMock

from bookmarker.models.bookmark import BookmarkStore

# Skip all tests if no display is available
pytestmark = pytest.mark.skipif(
    not bool(
        __import__("os").environ.get("DISPLAY") or
        __import__("os").environ.get("WAYLAND_DISPLAY")
    ),
    reason="No display available",
)


@pytest.fixture
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class TestBookmarkerApp:
    def test_app_creates(self, qapp, isolate_config):
        with patch("bookmarker.app.check_for_updates", return_value=None):
            from bookmarker.app import BookmarkerApp
            app = BookmarkerApp()
            assert app.windowTitle() == "Bookmarker"
            assert app.store is not None
            app._tray.hide()

    def test_app_has_tray(self, qapp, isolate_config):
        with patch("bookmarker.app.check_for_updates", return_value=None):
            from bookmarker.app import BookmarkerApp
            app = BookmarkerApp()
            assert app._tray is not None
            app._tray.hide()

    def test_app_loads_store(self, qapp, isolate_config):
        with patch("bookmarker.app.check_for_updates", return_value=None):
            from bookmarker.app import BookmarkerApp
            app = BookmarkerApp()
            assert "bookmark_bar" in app.store.roots
            assert "other" in app.store.roots
            app._tray.hide()

    def test_toggle_theme(self, qapp, isolate_config):
        with patch("bookmarker.app.check_for_updates", return_value=None):
            from bookmarker.app import BookmarkerApp
            from bookmarker.utils.theme import ThemeManager
            app = BookmarkerApp()
            original = ThemeManager.is_dark_mode()
            app._toggle_theme()
            assert ThemeManager.is_dark_mode() != original
            app._toggle_theme()  # Restore
            app._tray.hide()

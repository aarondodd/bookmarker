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

    def test_add_bookmark_from_clipboard_with_valid_url(self, qapp, isolate_config):
        with patch("bookmarker.app.check_for_updates", return_value=None):
            from bookmarker.app import BookmarkerApp
            from PyQt6.QtWidgets import QApplication
            app = BookmarkerApp()
            # Set clipboard to a valid URL
            clipboard = QApplication.clipboard()
            clipboard.setText("https://example.com/test")
            initial_count = len(app.store.all_bookmarks())
            app._add_bookmark_from_clipboard()
            # Should have added one bookmark
            assert len(app.store.all_bookmarks()) == initial_count + 1
            # Editor should be open
            assert app._editor is not None
            app._tray.hide()
            if app._editor:
                app._editor.close()

    def test_add_bookmark_from_clipboard_adds_https_prefix(self, qapp, isolate_config):
        with patch("bookmarker.app.check_for_updates", return_value=None):
            from bookmarker.app import BookmarkerApp
            from PyQt6.QtWidgets import QApplication
            app = BookmarkerApp()
            clipboard = QApplication.clipboard()
            clipboard.setText("example.com/page")
            app._add_bookmark_from_clipboard()
            # Should have added with https prefix
            matches = app.store.find_by_url("https://example.com/page")
            assert len(matches) == 1
            app._tray.hide()
            if app._editor:
                app._editor.close()

    def test_add_bookmark_from_clipboard_empty_shows_warning(self, qapp, isolate_config):
        with patch("bookmarker.app.check_for_updates", return_value=None):
            from bookmarker.app import BookmarkerApp
            from PyQt6.QtWidgets import QApplication, QMessageBox
            app = BookmarkerApp()
            clipboard = QApplication.clipboard()
            clipboard.setText("")
            initial_count = len(app.store.all_bookmarks())
            with patch.object(QMessageBox, "warning") as mock_warning:
                app._add_bookmark_from_clipboard()
                mock_warning.assert_called_once()
            # Should not have added any bookmark
            assert len(app.store.all_bookmarks()) == initial_count
            app._tray.hide()

    def test_add_bookmark_from_clipboard_invalid_shows_warning(self, qapp, isolate_config):
        with patch("bookmarker.app.check_for_updates", return_value=None):
            from bookmarker.app import BookmarkerApp
            from PyQt6.QtWidgets import QApplication, QMessageBox
            app = BookmarkerApp()
            clipboard = QApplication.clipboard()
            clipboard.setText("not a url at all")
            initial_count = len(app.store.all_bookmarks())
            with patch.object(QMessageBox, "warning") as mock_warning:
                app._add_bookmark_from_clipboard()
                mock_warning.assert_called_once()
            # Should not have added any bookmark
            assert len(app.store.all_bookmarks()) == initial_count
            app._tray.hide()

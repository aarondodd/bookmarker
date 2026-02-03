"""Tests for icon generation."""

import sys
import pytest
from unittest.mock import patch, MagicMock

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


class TestGenerateTrayIcon:
    def test_normal_icon(self, qapp):
        from bookmarker.utils.icon import generate_tray_icon
        icon = generate_tray_icon("normal", dark_mode=False)
        assert not icon.isNull()

    def test_syncing_icon(self, qapp):
        from bookmarker.utils.icon import generate_tray_icon
        icon = generate_tray_icon("syncing", dark_mode=False)
        assert not icon.isNull()

    def test_error_icon(self, qapp):
        from bookmarker.utils.icon import generate_tray_icon
        icon = generate_tray_icon("error", dark_mode=True)
        assert not icon.isNull()

    def test_dark_mode(self, qapp):
        from bookmarker.utils.icon import generate_tray_icon
        icon = generate_tray_icon("normal", dark_mode=True)
        assert not icon.isNull()

    def test_custom_size(self, qapp):
        from bookmarker.utils.icon import generate_tray_icon
        icon = generate_tray_icon("normal", size=128)
        assert not icon.isNull()

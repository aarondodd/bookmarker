"""Tests for theme management."""

from bookmarker.utils.theme import ThemeManager


class TestThemeManager:
    def test_default_is_light(self):
        assert ThemeManager.is_dark_mode() is False

    def test_dark_stylesheet_not_empty(self):
        assert len(ThemeManager.DARK_STYLESHEET) > 0

    def test_light_stylesheet_not_empty(self):
        assert len(ThemeManager.LIGHT_STYLESHEET) > 0

    def test_dark_stylesheet_contains_colors(self):
        assert "#1e1e1e" in ThemeManager.DARK_STYLESHEET

    def test_light_stylesheet_contains_colors(self):
        assert "#ffffff" in ThemeManager.LIGHT_STYLESHEET

    def test_set_dark_mode(self):
        original = ThemeManager.is_dark_mode()
        ThemeManager._dark_mode = True
        assert ThemeManager.is_dark_mode() is True
        ThemeManager._dark_mode = original

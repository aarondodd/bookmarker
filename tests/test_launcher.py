"""Tests for bookmark launcher utility."""

import pytest
from unittest.mock import patch, MagicMock

from bookmarker.models.bookmark import Bookmark, BookmarkType
from bookmarker.utils.launcher import open_url_in_browser, launch_bookmark


class TestOpenUrlInBrowser:
    def test_open_empty_url_returns_false(self):
        assert open_url_in_browser("") is False
        assert open_url_in_browser(None) is False

    def test_open_url_default_browser(self):
        with patch("bookmarker.utils.launcher.webbrowser.open") as mock_open:
            mock_open.return_value = True
            result = open_url_in_browser("https://example.com")
            assert result is True
            mock_open.assert_called_once_with("https://example.com")

    def test_open_url_default_browser_failure(self):
        with patch("bookmarker.utils.launcher.webbrowser.open") as mock_open:
            mock_open.side_effect = Exception("Failed")
            result = open_url_in_browser("https://example.com")
            assert result is False

    def test_open_url_specific_browser_not_found_falls_back(self):
        with patch("bookmarker.utils.launcher._find_browser_command", return_value=None):
            with patch("bookmarker.utils.launcher.webbrowser.open") as mock_open:
                mock_open.return_value = True
                result = open_url_in_browser("https://example.com", "chrome")
                assert result is True
                mock_open.assert_called_once_with("https://example.com")

    @patch("bookmarker.utils.launcher.platform.system", return_value="Linux")
    @patch("bookmarker.utils.launcher._find_browser_command", return_value="google-chrome")
    @patch("bookmarker.utils.launcher.subprocess.Popen")
    def test_open_url_linux_chrome(self, mock_popen, mock_find, mock_system):
        result = open_url_in_browser("https://example.com", "chrome")
        assert result is True
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args == ["google-chrome", "https://example.com"]


class TestLaunchBookmark:
    def test_launch_folder_returns_false(self):
        folder = Bookmark(title="Folder", type=BookmarkType.FOLDER)
        assert launch_bookmark(folder) is False

    def test_launch_empty_url_returns_false(self):
        bm = Bookmark(title="Empty", type=BookmarkType.URL, url="")
        assert launch_bookmark(bm) is False

    def test_launch_bookmark_uses_preferred_browser(self):
        bm = Bookmark(
            title="Test",
            type=BookmarkType.URL,
            url="https://example.com",
            preferred_browser="firefox"
        )
        with patch("bookmarker.utils.launcher.open_url_in_browser") as mock_open:
            mock_open.return_value = True
            result = launch_bookmark(bm)
            assert result is True
            mock_open.assert_called_once_with("https://example.com", "firefox")

    def test_launch_bookmark_default_browser(self):
        bm = Bookmark(
            title="Test",
            type=BookmarkType.URL,
            url="https://example.com",
        )
        with patch("bookmarker.utils.launcher.open_url_in_browser") as mock_open:
            mock_open.return_value = True
            result = launch_bookmark(bm)
            assert result is True
            mock_open.assert_called_once_with("https://example.com", None)

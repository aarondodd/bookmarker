"""Tests for browser detection."""

from pathlib import Path
from unittest.mock import patch, MagicMock

from bookmarker.operations.browser_detect import (
    BrowserInfo,
    detect_browsers,
    get_browser,
    is_browser_running,
    _get_firefox_default_profile,
    CHROME_PROCESS_NAMES,
    EDGE_PROCESS_NAMES,
    FIREFOX_PROCESS_NAMES,
)


class TestBrowserInfo:
    def test_dataclass_fields(self):
        info = BrowserInfo(
            name="chrome",
            display_name="Google Chrome",
            installed=True,
            running=False,
            bookmark_path=Path("/tmp/Bookmarks"),
            process_names=["chrome"],
        )
        assert info.name == "chrome"
        assert info.installed is True
        assert info.running is False


class TestIsRunning:
    def test_no_matching_processes(self):
        mock_proc = MagicMock()
        mock_proc.info = {"name": "bash"}
        with patch("bookmarker.operations.browser_detect.psutil.process_iter",
                    return_value=[mock_proc]):
            assert is_browser_running(CHROME_PROCESS_NAMES) is False

    def test_matching_process(self):
        mock_proc = MagicMock()
        mock_proc.info = {"name": "chrome"}
        with patch("bookmarker.operations.browser_detect.psutil.process_iter",
                    return_value=[mock_proc]):
            assert is_browser_running(CHROME_PROCESS_NAMES) is True

    def test_case_insensitive(self):
        mock_proc = MagicMock()
        mock_proc.info = {"name": "Chrome"}
        with patch("bookmarker.operations.browser_detect.psutil.process_iter",
                    return_value=[mock_proc]):
            assert is_browser_running(CHROME_PROCESS_NAMES) is True


class TestDetectBrowsers:
    def test_returns_three_browsers(self):
        with patch("bookmarker.operations.browser_detect._get_chrome_bookmark_path", return_value=None), \
             patch("bookmarker.operations.browser_detect._get_edge_bookmark_path", return_value=None), \
             patch("bookmarker.operations.browser_detect._get_firefox_bookmark_path", return_value=None), \
             patch("bookmarker.operations.browser_detect.is_browser_running", return_value=False):
            browsers = detect_browsers()
            assert len(browsers) == 3
            names = [b.name for b in browsers]
            assert "chrome" in names
            assert "edge" in names
            assert "firefox" in names

    def test_chrome_installed(self):
        with patch("bookmarker.operations.browser_detect._get_chrome_bookmark_path",
                    return_value=Path("/fake/Bookmarks")), \
             patch("bookmarker.operations.browser_detect._get_edge_bookmark_path", return_value=None), \
             patch("bookmarker.operations.browser_detect._get_firefox_bookmark_path", return_value=None), \
             patch("bookmarker.operations.browser_detect.is_browser_running", return_value=False):
            browsers = detect_browsers()
            chrome = [b for b in browsers if b.name == "chrome"][0]
            assert chrome.installed is True
            assert chrome.bookmark_path == Path("/fake/Bookmarks")


class TestGetBrowser:
    def test_get_chrome(self):
        with patch("bookmarker.operations.browser_detect._get_chrome_bookmark_path", return_value=None), \
             patch("bookmarker.operations.browser_detect._get_edge_bookmark_path", return_value=None), \
             patch("bookmarker.operations.browser_detect._get_firefox_bookmark_path", return_value=None), \
             patch("bookmarker.operations.browser_detect.is_browser_running", return_value=False):
            browser = get_browser("chrome")
            assert browser is not None
            assert browser.name == "chrome"

    def test_get_unknown(self):
        with patch("bookmarker.operations.browser_detect._get_chrome_bookmark_path", return_value=None), \
             patch("bookmarker.operations.browser_detect._get_edge_bookmark_path", return_value=None), \
             patch("bookmarker.operations.browser_detect._get_firefox_bookmark_path", return_value=None), \
             patch("bookmarker.operations.browser_detect.is_browser_running", return_value=False):
            browser = get_browser("opera")
            assert browser is None


class TestFirefoxProfile:
    def test_profiles_ini_parsing(self, tmp_path):
        profiles_dir = tmp_path / ".mozilla" / "firefox"
        profiles_dir.mkdir(parents=True)
        profile_dir = profiles_dir / "abc123.default-release"
        profile_dir.mkdir()
        (profile_dir / "places.sqlite").touch()

        ini_content = """[Profile0]
Name=default-release
IsRelative=1
Path=abc123.default-release
Default=1
"""
        (profiles_dir / "profiles.ini").write_text(ini_content)

        with patch("bookmarker.operations.browser_detect.platform.system", return_value="Linux"), \
             patch("bookmarker.operations.browser_detect.Path.home", return_value=tmp_path):
            result = _get_firefox_default_profile()
            assert result is not None
            assert result.name == "abc123.default-release"

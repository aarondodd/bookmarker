"""Bookmark launcher - open bookmarks in browsers."""

import platform
import subprocess
import webbrowser
from typing import Optional

from ..models.bookmark import Bookmark, BookmarkType


# Browser executable names by platform
BROWSER_COMMANDS = {
    "Linux": {
        "chrome": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
        "edge": ["microsoft-edge", "microsoft-edge-stable"],
        "firefox": ["firefox", "firefox-esr"],
    },
    "Windows": {
        "chrome": ["chrome"],
        "edge": ["msedge"],
        "firefox": ["firefox"],
    },
    "Darwin": {
        "chrome": ["Google Chrome"],
        "edge": ["Microsoft Edge"],
        "firefox": ["Firefox"],
    },
}


def _find_browser_command(browser_name: str) -> Optional[str]:
    """Find the executable command for a browser on this platform."""
    system = platform.system()
    commands = BROWSER_COMMANDS.get(system, {}).get(browser_name, [])

    if system == "Darwin":
        # macOS uses 'open -a' with app names
        for app_name in commands:
            try:
                result = subprocess.run(
                    ["mdfind", f"kMDItemKind == 'Application' && kMDItemDisplayName == '{app_name}'"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return app_name
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        return None

    # Linux/Windows: check if command exists
    for cmd in commands:
        try:
            if system == "Windows":
                result = subprocess.run(
                    ["where", cmd],
                    capture_output=True,
                    timeout=5,
                )
            else:
                result = subprocess.run(
                    ["which", cmd],
                    capture_output=True,
                    timeout=5,
                )
            if result.returncode == 0:
                return cmd
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    return None


def open_url_in_browser(url: str, browser: Optional[str] = None) -> bool:
    """Open a URL in the specified browser or system default.

    Args:
        url: The URL to open.
        browser: Browser name ("chrome", "edge", "firefox") or None for default.

    Returns:
        True if the browser was launched successfully.
    """
    if not url:
        return False

    system = platform.system()

    # Use system default if no browser specified
    if browser is None:
        try:
            webbrowser.open(url)
            return True
        except Exception:
            return False

    # Find the browser command
    browser_cmd = _find_browser_command(browser)
    if browser_cmd is None:
        # Fall back to system default
        try:
            webbrowser.open(url)
            return True
        except Exception:
            return False

    try:
        if system == "Darwin":
            # macOS: use 'open -a'
            subprocess.Popen(
                ["open", "-a", browser_cmd, url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif system == "Windows":
            # Windows: use start command
            subprocess.Popen(
                ["cmd", "/c", "start", "", browser_cmd, url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True,
            )
        else:
            # Linux: direct command
            subprocess.Popen(
                [browser_cmd, url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return True
    except Exception:
        # Fall back to system default
        try:
            webbrowser.open(url)
            return True
        except Exception:
            return False


def launch_bookmark(bookmark: Bookmark) -> bool:
    """Launch a bookmark in its preferred browser or system default.

    Args:
        bookmark: The bookmark to launch.

    Returns:
        True if launched successfully, False otherwise.
    """
    if bookmark.type != BookmarkType.URL:
        return False

    if not bookmark.url:
        return False

    return open_url_in_browser(bookmark.url, bookmark.preferred_browser)

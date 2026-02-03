"""Browser detection - installed browsers, running processes, bookmark paths."""

import configparser
import platform
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import psutil


@dataclass
class BrowserInfo:
    name: str  # "chrome", "edge", "firefox"
    display_name: str
    installed: bool
    running: bool
    bookmark_path: Optional[Path]
    process_names: List[str]


def _get_chrome_bookmark_path() -> Optional[Path]:
    """Get the Chrome bookmarks file path for the current platform."""
    system = platform.system()
    if system == "Linux":
        path = Path.home() / ".config" / "google-chrome" / "Default" / "Bookmarks"
    elif system == "Windows":
        local = os.environ.get("LOCALAPPDATA", "")
        path = Path(local) / "Google" / "Chrome" / "User Data" / "Default" / "Bookmarks"
    elif system == "Darwin":
        path = Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "Default" / "Bookmarks"
    else:
        return None
    return path if path.exists() else None


def _get_edge_bookmark_path() -> Optional[Path]:
    """Get the Edge bookmarks file path for the current platform."""
    system = platform.system()
    if system == "Linux":
        path = Path.home() / ".config" / "microsoft-edge" / "Default" / "Bookmarks"
    elif system == "Windows":
        local = os.environ.get("LOCALAPPDATA", "")
        path = Path(local) / "Microsoft" / "Edge" / "User Data" / "Default" / "Bookmarks"
    elif system == "Darwin":
        path = Path.home() / "Library" / "Application Support" / "Microsoft Edge" / "Default" / "Bookmarks"
    else:
        return None
    return path if path.exists() else None


def _get_firefox_profiles_dir() -> Optional[Path]:
    """Get the Firefox profiles directory."""
    system = platform.system()
    if system == "Linux":
        path = Path.home() / ".mozilla" / "firefox"
    elif system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        path = Path(appdata) / "Mozilla" / "Firefox" / "Profiles"
    elif system == "Darwin":
        path = Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles"
    else:
        return None
    return path if path.exists() else None


def _get_firefox_default_profile() -> Optional[Path]:
    """Find the default Firefox profile directory."""
    system = platform.system()
    if system == "Linux":
        profiles_ini = Path.home() / ".mozilla" / "firefox" / "profiles.ini"
    elif system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        profiles_ini = Path(appdata) / "Mozilla" / "Firefox" / "profiles.ini"
    elif system == "Darwin":
        profiles_ini = Path.home() / "Library" / "Application Support" / "Firefox" / "profiles.ini"
    else:
        return None

    if not profiles_ini.exists():
        return None

    config = configparser.ConfigParser()
    config.read(profiles_ini)

    # Look for default profile
    for section in config.sections():
        if not section.startswith("Profile") and section != "Install":
            continue
        if config.has_option(section, "Default") and config.get(section, "Default") == "1":
            if config.has_option(section, "Path"):
                is_relative = config.has_option(section, "IsRelative") and config.get(section, "IsRelative") == "1"
                profile_path = config.get(section, "Path")
                if is_relative:
                    return profiles_ini.parent / profile_path
                return Path(profile_path)

    # Fallback: look for any profile with places.sqlite
    if system == "Linux":
        base = Path.home() / ".mozilla" / "firefox"
    elif system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        base = Path(appdata) / "Mozilla" / "Firefox" / "Profiles"
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles"
    else:
        return None

    if base.exists():
        for entry in base.iterdir():
            if entry.is_dir() and (entry / "places.sqlite").exists():
                return entry
    return None


def _get_firefox_bookmark_path() -> Optional[Path]:
    """Get the Firefox places.sqlite path."""
    profile = _get_firefox_default_profile()
    if profile and (profile / "places.sqlite").exists():
        return profile / "places.sqlite"
    return None


CHROME_PROCESS_NAMES = ["chrome", "google-chrome", "google-chrome-stable", "chrome.exe"]
EDGE_PROCESS_NAMES = ["msedge", "microsoft-edge", "microsoft-edge-stable", "msedge.exe"]
FIREFOX_PROCESS_NAMES = ["firefox", "firefox.exe", "firefox-esr"]


def is_browser_running(process_names: List[str]) -> bool:
    """Check if any process matching the given names is running."""
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info["name"]
            if name and name.lower() in [p.lower() for p in process_names]:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def detect_browsers() -> List[BrowserInfo]:
    """Detect all supported browsers and their status."""
    browsers = []

    # Chrome
    chrome_path = _get_chrome_bookmark_path()
    browsers.append(BrowserInfo(
        name="chrome",
        display_name="Google Chrome",
        installed=chrome_path is not None,
        running=is_browser_running(CHROME_PROCESS_NAMES),
        bookmark_path=chrome_path,
        process_names=CHROME_PROCESS_NAMES,
    ))

    # Edge
    edge_path = _get_edge_bookmark_path()
    browsers.append(BrowserInfo(
        name="edge",
        display_name="Microsoft Edge",
        installed=edge_path is not None,
        running=is_browser_running(EDGE_PROCESS_NAMES),
        bookmark_path=edge_path,
        process_names=EDGE_PROCESS_NAMES,
    ))

    # Firefox
    firefox_path = _get_firefox_bookmark_path()
    browsers.append(BrowserInfo(
        name="firefox",
        display_name="Mozilla Firefox",
        installed=firefox_path is not None,
        running=is_browser_running(FIREFOX_PROCESS_NAMES),
        bookmark_path=firefox_path,
        process_names=FIREFOX_PROCESS_NAMES,
    ))

    return browsers


def get_browser(name: str) -> Optional[BrowserInfo]:
    """Get info for a specific browser by name."""
    for browser in detect_browsers():
        if browser.name == name:
            return browser
    return None

"""Auto-update functionality for Bookmarker.

Checks GitHub Releases API for new versions and can download/install updates.
Targets the aarondodd/bookmarker repository (public, no auth needed).
"""

import json
import os
import platform
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from .config import get_last_version_check, record_version_check, get_config_dir
from ..version import __version__

CHECK_INTERVAL_DAYS = 7
GITHUB_REPO = "aarondodd/bookmarker"
GITHUB_API_BASE = "https://api.github.com"


def should_check_for_updates() -> bool:
    """Determine if we should check for updates based on the last check time."""
    last_check = get_last_version_check()
    if last_check is None:
        return True
    return datetime.now() - last_check > timedelta(days=CHECK_INTERVAL_DAYS)


def parse_version(version_str: str) -> Optional[Tuple[int, ...]]:
    """Parse a version string into a tuple of integers for comparison."""
    if not version_str:
        return None

    try:
        if version_str.startswith("v"):
            version_str = version_str[1:]
        parts = version_str.split(".")
        return tuple(int(p) for p in parts)
    except (ValueError, AttributeError):
        return None


def is_newer_version(remote_version: str, local_version: str) -> bool:
    """Compare versions to determine if remote is newer than local."""
    remote_tuple = parse_version(remote_version)
    local_tuple = parse_version(local_version)

    if remote_tuple is None or local_tuple is None:
        return False

    return remote_tuple > local_tuple


def get_latest_release() -> Optional[Dict[str, Any]]:
    """Fetch the latest release information from GitHub."""
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/releases/latest"

    try:
        request = urllib.request.Request(url)
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("User-Agent", f"Bookmarker/{__version__}")

        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        tag_name = data.get("tag_name", "")

        # Find the source zip URL
        zip_url = data.get("zipball_url", "")

        return {
            "tag_name": tag_name.lstrip("v"),
            "zip_url": zip_url,
        }

    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        pass

    return None


def check_for_updates() -> Optional[Tuple[str, str]]:
    """Check for updates and return info if a newer version is available.

    Returns:
        Tuple of (local_version, remote_version) if update available,
        None otherwise.
    """
    if not should_check_for_updates():
        return None

    record_version_check()

    release_info = get_latest_release()
    if not release_info:
        return None

    remote_version = release_info["tag_name"]
    local_version = __version__

    if is_newer_version(remote_version, local_version):
        return (local_version, remote_version)

    return None


def download_release(zip_url: str, dest_path: str) -> bool:
    """Download the release archive from GitHub."""
    try:
        request = urllib.request.Request(zip_url)
        request.add_header("User-Agent", f"Bookmarker/{__version__}")

        with urllib.request.urlopen(request, timeout=120) as response:
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(response, f)

        return True

    except (urllib.error.URLError, urllib.error.HTTPError):
        return False


def extract_archive(zip_path: str, extract_dir: str) -> Optional[str]:
    """Extract the downloaded zip archive."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

        entries = os.listdir(extract_dir)
        if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
            return os.path.join(extract_dir, entries[0])
        else:
            return extract_dir

    except zipfile.BadZipFile:
        return None


def find_build_script(source_dir: str) -> Optional[str]:
    """Find the build script in the source directory."""
    system = platform.system()
    script_name = "build.ps1" if system == "Windows" else "build.sh"

    direct_path = os.path.join(source_dir, script_name)
    if os.path.exists(direct_path):
        return direct_path

    for root, dirs, files in os.walk(source_dir):
        depth = root[len(source_dir):].count(os.sep)
        if depth > 2:
            continue
        if script_name in files:
            return os.path.join(root, script_name)

    return None


def run_build_script(source_dir: str, output_callback=None) -> Tuple[bool, str]:
    """Run the appropriate build script from the extracted source."""
    system = platform.system()

    if system == "Windows":
        shell_cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File"]
    else:
        shell_cmd = ["bash"]

    script_path = find_build_script(source_dir)

    if not script_path:
        return False, f"Build script not found in {source_dir}"

    build_dir = os.path.dirname(script_path)

    if system != "Windows":
        os.chmod(script_path, 0o755)

    output_lines = []

    try:
        process = subprocess.Popen(
            shell_cmd + [script_path],
            cwd=build_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in process.stdout:
            line = line.rstrip("\n\r")
            output_lines.append(line)
            if output_callback:
                output_callback(line)

        process.wait()
        output_text = "\n".join(output_lines)

        if process.returncode == 0:
            return True, output_text
        else:
            return False, f"Build failed with return code {process.returncode}\n\n{output_text}"

    except Exception as e:
        return False, f"Error running build: {str(e)}"


def upgrade(progress_callback=None) -> Tuple[bool, str]:
    """Download and install the latest release."""

    def notify(stage, msg):
        if progress_callback:
            progress_callback(stage, msg)

    release_info = get_latest_release()
    if not release_info:
        return False, "Could not fetch release information from GitHub."

    remote_version = release_info["tag_name"]
    local_version = __version__

    if not is_newer_version(remote_version, local_version):
        return True, f"Already on the latest version ({local_version})."

    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, "bookmarker-release.zip")
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)

        notify("download", f"Downloading release {remote_version}...")
        if not download_release(release_info["zip_url"], zip_path):
            return False, "Failed to download release."

        notify("extract", "Extracting archive...")
        source_dir = extract_archive(zip_path, extract_dir)
        if not source_dir:
            return False, "Failed to extract release archive."

        bin_dir = os.path.join(Path.home(), "bin")
        app_name = "bookmarker"

        if platform.system() == "Windows":
            existing_exe = os.path.join(bin_dir, f"{app_name}.exe")
            upgrading_exe = os.path.join(bin_dir, f"{app_name}.exe.upgrading")
            if os.path.exists(upgrading_exe):
                try:
                    os.remove(upgrading_exe)
                except OSError:
                    pass
            if os.path.exists(existing_exe):
                try:
                    os.rename(existing_exe, upgrading_exe)
                    notify("build", "Renamed running executable for replacement...")
                except OSError:
                    pass
        else:
            existing_exe = os.path.join(bin_dir, app_name)
            if os.path.exists(existing_exe):
                try:
                    os.remove(existing_exe)
                    notify("build", "Removed existing executable for replacement...")
                except OSError:
                    pass

        notify("build", "Running build script...")

        def build_output_callback(line):
            notify("build_output", line)

        success, build_output = run_build_script(source_dir, build_output_callback)
        if not success:
            return False, f"Build failed:\n{build_output}"

    return True, f"Successfully upgraded from {local_version} to {remote_version}."

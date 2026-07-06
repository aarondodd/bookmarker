"""Auto-update functionality for Bookmarker.

Checks the GitHub Releases API for new versions and upgrades in place by
downloading the prebuilt release asset for the current platform -- no build
toolchain required on the user's machine. Targets the aarondodd/bookmarker
repository (public, no auth needed).

Three install kinds are handled (see ``install_kind``):

- ``windows-installer``: download ``bookmarker-setup-X.Y.Z.exe`` and run it
  silently. Inno Setup's stable AppId upgrades the install in place; the
  installer's CloseApplications + RestartApplications directives close the
  running app via Windows Restart Manager and relaunch it after.
- ``linux-tarball``: download ``bookmarker-linux-x86_64-X.Y.Z.tar.gz``, extract
  it beside the current onedir bundle, swap the directory in place, and re-exec
  the new launcher. A running Linux process tolerates its on-disk files being
  replaced, and the dir swap avoids editing live inodes.
- ``source``: running from source (not frozen). There is nothing to replace, so
  the updater reports that the user should update via their own workflow
  (git pull + build.sh / build.ps1) rather than silently kicking off a build.

Failures degrade gracefully (return ``(False, msg)`` or ``None``): private repo,
corporate MITM proxy, sandboxed DNS, or a release with no matching asset (CI
didn't run) all surface as "no update available" / a clear message.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import get_last_version_check, record_version_check
from ..version import __version__

CHECK_INTERVAL_DAYS = 7
GITHUB_REPO = "aarondodd/bookmarker"
GITHUB_API_BASE = "https://api.github.com"

USER_AGENT = f"Bookmarker/{__version__}"

# Asset filename patterns produced by .github/workflows/release.yml. The version
# capture verifies the asset matches the release tag.
WINDOWS_ASSET_PATTERN = re.compile(r"^bookmarker-setup-(?P<version>[\w.+-]+)\.exe$")
LINUX_ASSET_PATTERN = re.compile(
    r"^bookmarker-linux-x86_64-(?P<version>[\w.+-]+)\.tar\.gz$"
)


# --------- install-kind detection ------------------------------------------


def is_frozen() -> bool:
    """True iff this Python is running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def install_kind() -> str:
    """Classify how this Bookmarker was installed.

    Returns one of: ``"source"`` (not frozen), ``"windows-installer"``,
    ``"linux-tarball"``, ``"unknown"`` (frozen on an unsupported platform).
    """
    if not is_frozen():
        return "source"
    if sys.platform.startswith("win"):
        return "windows-installer"
    if sys.platform.startswith("linux"):
        return "linux-tarball"
    return "unknown"


def current_bundle_dir() -> Optional[Path]:
    """Directory of the running onedir bundle, or None when not frozen.

    Under PyInstaller --onedir, ``sys.executable`` is the launcher inside
    dist/bookmarker/, so its parent is the swappable bundle directory.
    """
    if not is_frozen():
        return None
    try:
        return Path(sys.executable).resolve().parent
    except OSError:
        return None


# --------- version comparison ----------------------------------------------


def parse_version(version_str: str) -> Optional[Tuple[int, ...]]:
    """Parse 'v1.2.3' or '1.2.3[-pre]' into (1, 2, 3). Returns None on failure.

    Strips a leading 'v' and any pre-release/build suffix, so '0.1.4-dev'
    compares equal to '0.1.4'.
    """
    if not version_str:
        return None
    cleaned = version_str.strip()
    if cleaned[:1] in ("v", "V"):
        cleaned = cleaned[1:]
    for sep in ("-", "+"):
        if sep in cleaned:
            cleaned = cleaned.split(sep, 1)[0]
    try:
        return tuple(int(p) for p in cleaned.split("."))
    except (ValueError, AttributeError):
        return None


def is_newer_version(remote_version: str, local_version: str) -> bool:
    """True iff `remote_version` parses to a strictly higher tuple."""
    remote = parse_version(remote_version)
    local = parse_version(local_version)
    if remote is None or local is None:
        return False
    return remote > local


# --------- check + fetch ----------------------------------------------------


def should_check_for_updates() -> bool:
    """True if we haven't checked in CHECK_INTERVAL_DAYS days."""
    last_check = get_last_version_check()
    if last_check is None:
        return True
    return datetime.now() - last_check > timedelta(days=CHECK_INTERVAL_DAYS)


def get_latest_release() -> Optional[Dict[str, Any]]:
    """Fetch the latest release from GitHub. Returns dict on success, else None.

    Shape: {"tag_name": "0.1.4", "assets": [...], "html_url": str, "body": str}.
    Returns None on any network/parse failure (404 included). Callers treat
    None as "no update available".
    """
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/releases/latest"
    request = urllib.request.Request(url)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("User-Agent", USER_AGENT)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError):
        return None

    tag = data.get("tag_name", "")
    if not tag:
        return None
    return {
        "tag_name": tag.lstrip("vV"),
        "assets": data.get("assets", []),
        "html_url": data.get("html_url", ""),
        "body": data.get("body", ""),
    }


def find_asset(release: Dict[str, Any], pattern: re.Pattern) -> Optional[Tuple[str, str]]:
    """Locate the first release asset whose name matches `pattern`.

    Returns (version, browser_download_url) or None if no asset matches (the
    release was created without the workflow, the workflow failed before upload,
    or the platform's asset is missing).
    """
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        match = pattern.match(name)
        if not match:
            continue
        url = asset.get("browser_download_url", "")
        if not url:
            continue
        return (match.group("version"), url)
    return None


def check_for_updates() -> Optional[Tuple[str, str]]:
    """Auto-check entry point. Returns (local, remote) if a newer release exists.

    Respects the weekly interval and stamps the last-check time as a side
    effect. Returns None if the interval hasn't elapsed or no newer release.
    """
    if not should_check_for_updates():
        return None
    record_version_check()
    release = get_latest_release()
    if not release:
        return None
    if is_newer_version(release["tag_name"], __version__):
        return (__version__, release["tag_name"])
    return None


# --------- download + cache -------------------------------------------------


def updates_dir() -> Path:
    """Per-user directory where downloaded release assets are cached."""
    # Reference through the config module (not the imported name) so tests that
    # monkeypatch config.get_config_dir isolate this directory too.
    from . import config

    path = config.get_config_dir() / "updates"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path


def prune_updates_cache(*, keep_newest: int = 1) -> List[Path]:
    """Delete cached downloaded assets except the ``keep_newest`` most recent.

    The updater downloads each release's installer/tarball to updates_dir()
    and never sweeps the old ones. Call on startup to keep the cache bounded.
    Returns the paths deleted (best-effort; unlink failures are skipped).
    """
    cache = updates_dir()
    if not cache.is_dir():
        return []
    assets = [
        p
        for p in cache.iterdir()
        if p.is_file()
        and (
            WINDOWS_ASSET_PATTERN.match(p.name)
            or LINUX_ASSET_PATTERN.match(p.name)
        )
    ]
    assets.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    deleted: List[Path] = []
    for asset in assets[max(0, keep_newest):]:
        try:
            asset.unlink()
            deleted.append(asset)
        except OSError:
            pass
    return deleted


def download_release(url: str, dest_path: Path) -> bool:
    """Stream a release asset to dest_path. Returns True on success."""
    request = urllib.request.Request(url)
    request.add_header("User-Agent", USER_AGENT)
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(response, f)
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return False


# --------- Windows: installer-driven upgrade --------------------------------


def launch_installer(installer_path: Path) -> Tuple[bool, str]:
    """Spawn the Inno Setup installer silently and return immediately.

    Runs detached so its lifetime survives this process exiting. /SILENT
    suppresses the wizard, /SUPPRESSMSGBOXES auto-confirms prompts, /NORESTART
    keeps Inno from requesting a reboot. installer.iss's CloseApplications +
    RestartApplications handle the "app is running" case via Restart Manager
    and relaunch the app after install.
    """
    if not installer_path.exists():
        return False, f"Installer not found at {installer_path}."
    cmd = [str(installer_path), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
    kwargs: Dict[str, Any] = {}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
        kwargs["close_fds"] = True
    try:
        subprocess.Popen(cmd, **kwargs)
    except OSError as exc:
        return False, f"Could not launch installer: {exc}"
    return True, f"Installer launched: {installer_path.name}"


def _upgrade_windows(
    release: Dict[str, Any], notify: Callable[[str, str], None]
) -> Tuple[bool, str]:
    asset = find_asset(release, WINDOWS_ASSET_PATTERN)
    if asset is None:
        ver = release["tag_name"]
        return False, (
            f"Release {ver} exists but has no Windows installer asset "
            f"(expected bookmarker-setup-{ver}.exe). The release workflow may "
            f"have failed; check https://github.com/{GITHUB_REPO}/releases."
        )
    asset_version, asset_url = asset
    installer_path = updates_dir() / f"bookmarker-setup-{asset_version}.exe"

    notify("download", f"Downloading installer for {release['tag_name']}...")
    if not download_release(asset_url, installer_path):
        return False, "Failed to download installer."

    notify("launch", f"Launching installer for {release['tag_name']}...")
    ok, msg = launch_installer(installer_path)
    if not ok:
        return False, f"{msg}\n\nDownloaded installer: {installer_path}"

    notify("done", f"Installer launched for {release['tag_name']}.")
    return True, (
        f"Installer for {release['tag_name']} has been launched silently. "
        "Bookmarker will close shortly; Windows Restart Manager handles the "
        "upgrade and relaunches the app when the install completes."
    )


# --------- Linux: tarball dir-swap upgrade ----------------------------------


def _find_extracted_bundle(extract_dir: Path) -> Optional[Path]:
    """Locate the bundle root inside an extracted tarball.

    The tarball packs the ``bookmarker/`` directory, so the launcher lives at
    ``<extract_dir>/bookmarker/bookmarker``. Fall back to a shallow search in
    case the archive layout shifts.
    """
    direct = extract_dir / "bookmarker"
    if (direct / "bookmarker").exists():
        return direct
    for root, _dirs, files in os.walk(extract_dir):
        if "bookmarker" in files:
            return Path(root)
    return None


def _upgrade_linux(
    release: Dict[str, Any], notify: Callable[[str, str], None]
) -> Tuple[bool, str]:
    asset = find_asset(release, LINUX_ASSET_PATTERN)
    if asset is None:
        ver = release["tag_name"]
        return False, (
            f"Release {ver} exists but has no Linux asset (expected "
            f"bookmarker-linux-x86_64-{ver}.tar.gz). The release workflow may "
            f"have failed; check https://github.com/{GITHUB_REPO}/releases."
        )
    asset_version, asset_url = asset

    bundle_dir = current_bundle_dir()
    if bundle_dir is None:
        return False, "Could not locate the running bundle directory."

    install_root = bundle_dir.parent
    if not os.access(install_root, os.W_OK):
        # Downloaded but can't swap (e.g. installed under /opt as root).
        tarball_path = updates_dir() / f"bookmarker-linux-x86_64-{asset_version}.tar.gz"
        download_release(asset_url, tarball_path)
        return False, (
            f"Cannot write to {install_root}; automatic upgrade needs write "
            f"access to the install directory. Downloaded the new build to "
            f"{tarball_path} -- extract it over {bundle_dir} manually."
        )

    tarball_path = updates_dir() / f"bookmarker-linux-x86_64-{asset_version}.tar.gz"
    notify("download", f"Downloading {release['tag_name']}...")
    if not download_release(asset_url, tarball_path):
        return False, "Failed to download release archive."

    notify("extract", "Extracting archive...")
    staging = Path(tempfile.mkdtemp(prefix="bookmarker-upd-", dir=str(install_root)))
    try:
        with tarfile.open(tarball_path, "r:gz") as tf:
            tf.extractall(staging)
    except (tarfile.TarError, OSError) as exc:
        shutil.rmtree(staging, ignore_errors=True)
        return False, f"Failed to extract archive: {exc}"

    new_bundle = _find_extracted_bundle(staging)
    if new_bundle is None or not (new_bundle / "bookmarker").exists():
        shutil.rmtree(staging, ignore_errors=True)
        return False, "Extracted archive did not contain a bookmarker launcher."

    # Atomic-ish swap: move the old bundle aside, move the new one in, then
    # re-exec the fresh launcher. Old dir is cleaned up on the next startup.
    notify("build", "Swapping in the new build...")
    old_dir = install_root / f"{bundle_dir.name}.old"
    shutil.rmtree(old_dir, ignore_errors=True)
    try:
        os.rename(bundle_dir, old_dir)
        os.rename(new_bundle, bundle_dir)
    except OSError as exc:
        # Best-effort rollback so we never leave the app without a bundle.
        if not bundle_dir.exists() and old_dir.exists():
            try:
                os.rename(old_dir, bundle_dir)
            except OSError:
                pass
        shutil.rmtree(staging, ignore_errors=True)
        return False, f"Failed to swap in the new build: {exc}"

    shutil.rmtree(staging, ignore_errors=True)

    new_launcher = bundle_dir / "bookmarker"
    notify("done", f"Upgraded to {release['tag_name']}; relaunching...")
    try:
        os.chmod(new_launcher, 0o755)
        os.execv(str(new_launcher), [str(new_launcher), *sys.argv[1:]])
    except OSError as exc:
        return False, (
            f"Upgraded to {release['tag_name']}, but could not relaunch "
            f"automatically ({exc}). Restart Bookmarker manually."
        )
    return True, f"Upgraded to {release['tag_name']}."  # not reached after execv


def cleanup_stale_bundle() -> None:
    """Remove a leftover ``<bundle>.old`` directory from a prior Linux upgrade.

    Safe to call unconditionally on startup; a no-op when not frozen, not on
    Linux, or nothing to clean.
    """
    if install_kind() != "linux-tarball":
        return
    bundle_dir = current_bundle_dir()
    if bundle_dir is None:
        return
    old_dir = bundle_dir.parent / f"{bundle_dir.name}.old"
    if old_dir.is_dir():
        shutil.rmtree(old_dir, ignore_errors=True)


# --------- public upgrade entry point ---------------------------------------


def upgrade(progress_callback=None) -> Tuple[bool, str]:
    """Download and install the latest release for the current platform.

    progress_callback receives (stage, message) tuples; stages are one of
    'fetch', 'download', 'extract', 'build', 'launch', 'done'.

    Returns (True, msg) when the upgrade has been handed off (installer
    launched / new build re-exec'd); (False, msg) on any failure or when
    running from source.
    """

    def notify(stage: str, msg: str) -> None:
        if progress_callback:
            progress_callback(stage, msg)

    kind = install_kind()
    if kind == "source":
        return False, (
            "This Bookmarker is running from source, not a packaged build. The "
            "built-in updater only upgrades installer/tarball-managed installs.\n\n"
            "To update a source checkout, use your own workflow: git pull, then "
            "./build.sh (Linux/macOS) or .\\build.ps1 (Windows)."
        )
    if kind == "unknown":
        return False, (
            "Automatic upgrade is only supported on Windows and Linux builds. "
            f"Download the latest release from https://github.com/{GITHUB_REPO}/releases."
        )

    notify("fetch", "Checking GitHub for the latest release...")
    release = get_latest_release()
    if not release:
        return False, "Could not fetch release information (check network connectivity)."

    if not is_newer_version(release["tag_name"], __version__):
        return True, f"Already on the latest version ({__version__})."

    if kind == "windows-installer":
        return _upgrade_windows(release, notify)
    return _upgrade_linux(release, notify)

"""Extract the bundled extension to user space and register the native-messaging
host so a running Bookmarker can talk to the extension.

Install path is "guided manual": the app puts the files where the browser can
find them (extension folder on disk + native-host manifest + registration), and
the user loads the unpacked extension once from ``chrome://extensions``. This is
the same tradeoff meeting-notetaker made for a personal tool.

The native-host manifest's ``allowed_origins`` pins the single deterministic
extension ID derived from the manifest ``key``. A mismatch is caught at extract
time by :func:`extract_extension` rather than surfacing as a silent runtime
rejection.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.config import automation_dir, extension_dir
from ..version import __version__

log = logging.getLogger(__name__)

NATIVE_HOST_NAME = "org.aarondodd.bookmarker.sync"

# Deterministic extension ID derived from the SPKI public key embedded in
# resources/extension/manifest.json's ``key``. If that key changes, this must
# change too -- they are a pair (validated in extract_extension).
EXTENSION_ID = "cckjffdjcffgggmdjamiabnpebegdmcg"

# Chromium-family browsers we register for. name -> (linux dir, mac dir, HKCU key)
_BROWSERS: Dict[str, Dict[str, str]] = {
    "chrome": {
        "linux": ".config/google-chrome/NativeMessagingHosts",
        "mac": "Library/Application Support/Google/Chrome/NativeMessagingHosts",
        "hkcu": r"Software\Google\Chrome\NativeMessagingHosts",
    },
    "chromium": {
        "linux": ".config/chromium/NativeMessagingHosts",
        "mac": "Library/Application Support/Chromium/NativeMessagingHosts",
        "hkcu": r"Software\Chromium\NativeMessagingHosts",
    },
    "edge": {
        "linux": ".config/microsoft-edge/NativeMessagingHosts",
        "mac": "Library/Application Support/Microsoft Edge/NativeMessagingHosts",
        "hkcu": r"Software\Microsoft\Edge\NativeMessagingHosts",
    },
}


# --------------------------------------------------------------------- resources


def _home() -> Path:
    """Indirection over Path.home() so tests can redirect manifest writes away
    from the real ~/.config."""
    return Path.home()


def _bundled_extension_source() -> Path:
    """Locate the extension folder shipped with the app (source tree or frozen
    bundle)."""
    here = Path(__file__).resolve().parent.parent  # bookmarker/
    candidate = here / "resources" / "extension"
    if candidate.exists():
        return candidate
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass) / "bookmarker" / "resources" / "extension"
        if bundled.exists():
            return bundled
    return candidate


def bundled_extension_version() -> str:
    target = _bundled_extension_source() / "manifest.json"
    if not target.is_file():
        return ""
    try:
        return str(json.loads(target.read_text(encoding="utf-8")).get("version") or "")
    except (OSError, ValueError):
        return ""


def installed_extension_version() -> str:
    target = extension_dir() / "manifest.json"
    if not target.is_file():
        return ""
    try:
        return str(json.loads(target.read_text(encoding="utf-8")).get("version") or "")
    except (OSError, ValueError):
        return ""


def _derive_extension_id_from_key(key_b64: str) -> str:
    """Replicate Chrome's derivation: SHA256 of the raw SPKI bytes, first 16
    bytes, each nibble mapped to a letter a-p."""
    raw = base64.b64decode(key_b64)
    digest = hashlib.sha256(raw).digest()[:16]
    return "".join(chr(ord("a") + (b >> 4)) + chr(ord("a") + (b & 0xF)) for b in digest)


def extract_extension(*, source: Optional[Path] = None, dest: Optional[Path] = None) -> Path:
    """Copy the bundled extension to user space. Re-extracting is safe."""
    source = source or _bundled_extension_source()
    dest = dest or extension_dir()
    if not (source / "manifest.json").exists():
        raise FileNotFoundError(f"bundled extension missing at {source}")
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest)
    manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    key_b64 = manifest.get("key", "")
    if key_b64:
        derived = _derive_extension_id_from_key(key_b64)
        if derived != EXTENSION_ID:
            raise ValueError(
                f"extension key/id mismatch: manifest key derives to {derived!r} "
                f"but installer.EXTENSION_ID is {EXTENSION_ID!r}. Update one or the other."
            )
    return dest


# --------------------------------------------------------------------- host manifest


def default_host_command() -> tuple[Path, List[str]]:
    """Return (executable, args) that launch the native host.

    Frozen: the bookmarker exe with ``--native-host``. From source: the current
    Python interpreter running ``main.py --native-host``.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable), ["--native-host"]
    main_py = Path(__file__).resolve().parents[2] / "main.py"
    return Path(sys.executable), [str(main_py), "--native-host"]


def _write_wrapper(host_executable: Path, host_args: List[str]) -> Path:
    """Chrome invokes the manifest ``path`` with no args, so point it at a tiny
    wrapper that adds ``--native-host``."""
    if sys.platform.startswith("win"):
        wrapper = automation_dir() / "native_host.cmd"
        body = (
            "@echo off\r\n"
            f'"{host_executable}" {" ".join(host_args)} %*\r\n'
        )
        wrapper.write_text(body, encoding="utf-8")
    else:
        wrapper = automation_dir() / "native_host.sh"
        args = " ".join(f'"{a}"' for a in host_args)
        body = "#!/usr/bin/env bash\n" f'exec "{host_executable}" {args} "$@"\n'
        wrapper.write_text(body, encoding="utf-8")
        wrapper.chmod(0o755)
    return wrapper


def _manifest_dict(wrapper_path: Path) -> Dict[str, Any]:
    return {
        "name": NATIVE_HOST_NAME,
        "description": "Bookmarker browser-sync bridge: keeps browser bookmarks "
        "in sync with the Bookmarker desktop app.",
        "path": str(wrapper_path),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{EXTENSION_ID}/"],
    }


def write_native_host_manifest(*, host_executable: Path, host_args: List[str]) -> List[Path]:
    """Write the native-host manifest to every Chromium-family location for the
    current OS. On Windows also register the HKCU keys. Returns the manifest
    paths written."""
    wrapper = _write_wrapper(host_executable, host_args)
    manifest = _manifest_dict(wrapper)
    body = json.dumps(manifest, indent=2)

    written: List[Path] = []
    if sys.platform.startswith("win"):
        # One canonical manifest under automation_dir(); registry points at it.
        canonical = automation_dir() / f"{NATIVE_HOST_NAME}.json"
        canonical.write_text(body, encoding="utf-8")
        written.append(canonical)
        _register_windows(canonical)
    else:
        home = _home()
        key = "mac" if sys.platform == "darwin" else "linux"
        for browser in _BROWSERS.values():
            dest_dir = home / browser[key]
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"{NATIVE_HOST_NAME}.json"
            dest.write_text(body, encoding="utf-8")
            written.append(dest)
    return written


def _register_windows(manifest_path: Path) -> List[str]:
    if not sys.platform.startswith("win"):
        return []
    import winreg  # type: ignore[import-not-found]  # noqa: PLC0415

    done: List[str] = []
    for browser in _BROWSERS.values():
        full = rf"{browser['hkcu']}\{NATIVE_HOST_NAME}"
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, full) as k:
                winreg.SetValue(k, "", winreg.REG_SZ, str(manifest_path))
            done.append(rf"HKCU\{full}")
        except OSError as exc:
            log.warning("registry write %s failed: %s", full, exc)
    return done


def _unregister_windows() -> None:
    if not sys.platform.startswith("win"):
        return
    import winreg  # type: ignore[import-not-found]  # noqa: PLC0415

    for browser in _BROWSERS.values():
        full = rf"{browser['hkcu']}\{NATIVE_HOST_NAME}"
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, full)
        except FileNotFoundError:
            pass
        except OSError as exc:
            log.warning("registry delete %s failed: %s", full, exc)


# --------------------------------------------------------------------- state


def native_host_manifest_paths() -> List[Path]:
    """The manifest locations we would write, for state reporting."""
    if sys.platform.startswith("win"):
        return [automation_dir() / f"{NATIVE_HOST_NAME}.json"]
    home = _home()
    key = "mac" if sys.platform == "darwin" else "linux"
    return [home / b[key] / f"{NATIVE_HOST_NAME}.json" for b in _BROWSERS.values()]


def installation_state() -> Dict[str, Any]:
    ext_ok = (extension_dir() / "manifest.json").exists()
    manifests = native_host_manifest_paths()
    return {
        "extension_extracted": ext_ok,
        "extension_path": str(extension_dir()),
        "extension_id": EXTENSION_ID,
        "native_manifest_written": any(p.exists() for p in manifests),
        "native_manifest_paths": [str(p) for p in manifests],
        "bundled_version": bundled_extension_version(),
        "installed_version": installed_extension_version(),
    }


def is_fully_installed() -> bool:
    s = installation_state()
    return bool(s["extension_extracted"] and s["native_manifest_written"])


# --------------------------------------------------------------------- orchestration


def install(*, host_executable: Optional[Path] = None, host_args: Optional[List[str]] = None) -> Dict[str, Any]:
    """End-to-end install. Idempotent."""
    if host_executable is None or host_args is None:
        host_executable, host_args = default_host_command()
    extract_extension()
    write_native_host_manifest(host_executable=host_executable, host_args=host_args)
    return installation_state()


def uninstall(*, keep_extension_files: bool = True) -> Dict[str, Any]:
    """Tear down registration. Leaves the extension folder by default (the user
    owns the chrome://extensions toggle)."""
    if sys.platform.startswith("win"):
        _unregister_windows()
    for path in native_host_manifest_paths():
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    if not keep_extension_files:
        try:
            shutil.rmtree(extension_dir())
        except FileNotFoundError:
            pass
    return installation_state()

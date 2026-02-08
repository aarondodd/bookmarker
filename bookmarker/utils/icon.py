"""Icon generation for Bookmarker system tray."""

import shutil
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QIcon

# Pre-rendered bookmark icon bundled with the package
_ICON_SOURCE = Path(__file__).parent / "bookmark.png"

_ICON_NAME = "bookmarker"

_icon_cache = None
_linux_installed = False


def _install_to_user_icon_theme():
    """Install the icon into ~/.local/share/icons/hicolor/ for Linux SNI.

    Linux system trays using the StatusNotifierItem D-Bus protocol look up
    icons by name from the freedesktop icon theme. Installing to the user's
    hicolor theme ensures the tray host process can find the icon when Qt
    sends the IconName property over D-Bus.
    """
    global _linux_installed
    if _linux_installed:
        return
    _linux_installed = True

    if not _ICON_SOURCE.exists():
        return

    source_pixmap = QPixmap(str(_ICON_SOURCE))
    icon_base = Path.home() / ".local" / "share" / "icons" / "hicolor"

    for size in (16, 22, 24, 32, 48, 64):
        dest_dir = icon_base / f"{size}x{size}" / "apps"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{_ICON_NAME}.png"
        scaled = source_pixmap.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.save(str(dest), "PNG")


def generate_tray_icon(
    state: str = "normal",
    dark_mode: bool = False,
    size: int = 64,
) -> QIcon:
    """Return a bookmark ribbon icon for the system tray.

    On Linux, installs the icon to the user's freedesktop icon theme
    and returns QIcon.fromTheme() so the SNI D-Bus protocol can
    communicate the icon by name. Falls back to direct file load.

    On Windows, loads the bundled PNG directly.
    """
    global _icon_cache
    if _icon_cache is not None:
        return _icon_cache

    if sys.platform.startswith("linux"):
        _install_to_user_icon_theme()
        icon = QIcon.fromTheme(_ICON_NAME)
        if not icon.isNull():
            _icon_cache = icon
            return _icon_cache

    _icon_cache = QIcon(str(_ICON_SOURCE))
    return _icon_cache

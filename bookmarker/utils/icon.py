"""Icon generation for Bookmarker system tray."""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QColor, QIcon, QPen, QBrush, QPainterPath

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


def _generate_painted_icon(
    state: str = "normal",
    dark_mode: bool = False,
    size: int = 64,
) -> QIcon:
    """Generate a bookmark ribbon icon using QPainter.

    Used on Windows where the icon is drawn dynamically to support
    state-dependent colors (normal, syncing, error).
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    margin = max(2, size // 8)
    w = size - 2 * margin
    h = size - 2 * margin
    x = margin
    y = margin

    # Colors based on state
    if state == "error":
        fill_color = QColor("#f44336")
        border_color = QColor("#b71c1c")
    elif state == "syncing":
        fill_color = QColor("#2196f3")
        border_color = QColor("#1565c0")
    else:
        if dark_mode:
            fill_color = QColor("#e0e0e0")
            border_color = QColor("#9e9e9e")
        else:
            fill_color = QColor("#424242")
            border_color = QColor("#212121")

    # Draw bookmark ribbon shape
    path = QPainterPath()
    notch_depth = h * 0.2
    corner_radius = w * 0.15

    # Start at top-left, draw rounded top
    path.moveTo(x + corner_radius, y)
    path.lineTo(x + w - corner_radius, y)
    path.quadTo(x + w, y, x + w, y + corner_radius)
    # Right side down
    path.lineTo(x + w, y + h - notch_depth)
    # Notch (V shape at bottom)
    path.lineTo(x + w / 2, y + h - notch_depth * 2)
    path.lineTo(x, y + h - notch_depth)
    # Left side up
    path.lineTo(x, y + corner_radius)
    path.quadTo(x, y, x + corner_radius, y)
    path.closeSubpath()

    painter.setBrush(QBrush(fill_color))
    pen = QPen(border_color, max(1, size // 32))
    painter.setPen(pen)
    painter.drawPath(path)

    painter.end()

    return QIcon(pixmap)


def generate_tray_icon(
    state: str = "normal",
    dark_mode: bool = False,
    size: int = 64,
) -> QIcon:
    """Return a bookmark ribbon icon for the system tray.

    On Linux, installs the icon to the user's freedesktop icon theme
    and returns QIcon.fromTheme() so the SNI D-Bus protocol can
    communicate the icon by name. Falls back to direct file load.

    On Windows, generates the icon dynamically with QPainter.
    """
    if sys.platform.startswith("linux"):
        global _icon_cache
        if _icon_cache is not None:
            return _icon_cache

        _install_to_user_icon_theme()
        icon = QIcon.fromTheme(_ICON_NAME)
        if not icon.isNull():
            _icon_cache = icon
            return _icon_cache

        _icon_cache = QIcon(str(_ICON_SOURCE))
        return _icon_cache

    # Windows/macOS: generate dynamically (supports state/theme changes)
    return _generate_painted_icon(state, dark_mode, size)

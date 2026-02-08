"""Icon generation for Bookmarker system tray."""

import os
import sys
import tempfile

from PyQt6.QtCore import Qt, QRect, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QFont, QColor, QIcon, QPen, QBrush, QPainterPath, QImage

# On Linux, AppIndicator/SNI tray backends transmit icon identity over D-Bus
# using the icon's theme name (IconName property), not raw pixel data. Icons
# created from in-memory pixmaps have no theme name, so the SNI host shows a
# "missing icon" placeholder. The fix is to save icons into a proper
# freedesktop icon theme directory and use QIcon.fromTheme(), which gives the
# icon a name that the SNI protocol can communicate to the host process.
_icon_theme_dir = None

_ICON_SIZES = (16, 22, 24, 32, 48, 64)


def _ensure_linux_icon_theme():
    """Create a temporary icon theme directory for SNI tray compatibility."""
    global _icon_theme_dir
    if _icon_theme_dir is not None:
        return

    _icon_theme_dir = tempfile.mkdtemp(prefix="bookmarker_icons_")
    theme_dir = os.path.join(_icon_theme_dir, "hicolor")

    for size in _ICON_SIZES:
        os.makedirs(os.path.join(theme_dir, f"{size}x{size}", "apps"))

    # Write index.theme so this works even if system hicolor is absent
    dirs_str = ",".join(f"{s}x{s}/apps" for s in _ICON_SIZES)
    lines = [f"[Icon Theme]", f"Name=hicolor", f"Directories={dirs_str}", ""]
    for s in _ICON_SIZES:
        lines.extend([f"[{s}x{s}/apps]", f"Size={s}", f"Type=Fixed", ""])

    with open(os.path.join(theme_dir, "index.theme"), "w") as f:
        f.write("\n".join(lines))

    # Append to search paths (after system dirs so we don't override the
    # system hicolor index.theme when it exists)
    paths = QIcon.themeSearchPaths()
    QIcon.setThemeSearchPaths(paths + [_icon_theme_dir])


def _render_icon_image(state: str, dark_mode: bool, size: int) -> QImage:
    """Render the bookmark ribbon icon to a QImage at the given size."""
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
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
    return image


def generate_tray_icon(
    state: str = "normal",
    dark_mode: bool = False,
    size: int = 64,
) -> QIcon:
    """Generate a bookmark ribbon icon for the system tray.

    The icon is a ribbon/bookmark shape.
    Background color changes for syncing/error states.

    Args:
        state: One of 'normal', 'syncing', 'error'.
        dark_mode: Whether the OS is in dark mode.
        size: Icon size in pixels.

    Returns:
        QIcon ready for use as a system tray icon.
    """
    if sys.platform.startswith("linux"):
        _ensure_linux_icon_theme()

        icon_name = f"bookmarker-tray-{state}-{'dark' if dark_mode else 'light'}"

        # Render and save at all standard icon sizes
        for s in _ICON_SIZES:
            img = _render_icon_image(state, dark_mode, s)
            icon_path = os.path.join(
                _icon_theme_dir, "hicolor", f"{s}x{s}", "apps", f"{icon_name}.png"
            )
            img.save(icon_path, "PNG")

        icon = QIcon.fromTheme(icon_name)
        if not icon.isNull():
            return icon

        # Fallback if theme lookup fails: use direct file path
        fallback_path = os.path.join(
            _icon_theme_dir, "hicolor", "64x64", "apps", f"{icon_name}.png"
        )
        return QIcon(fallback_path)

    image = _render_icon_image(state, dark_mode, size)
    pixmap = QPixmap.fromImage(image)
    return QIcon(pixmap)

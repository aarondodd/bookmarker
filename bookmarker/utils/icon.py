"""Icon generation for Bookmarker system tray."""

import sys

from PyQt6.QtCore import Qt, QRect, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QFont, QColor, QIcon, QPen, QBrush, QPainterPath, QImage

_IS_LINUX = sys.platform.startswith("linux")


def generate_tray_icon(
    state: str = "normal",
    dark_mode: bool = False,
    size: int = 64,
) -> QIcon:
    """Generate a bookmark ribbon icon for the system tray.

    The icon is a ribbon/bookmark shape.
    Background color changes for syncing/error states.

    On Linux, icons use an opaque rounded-rect background with a white
    bookmark ribbon, since many Linux system trays do not reliably
    support icon transparency.

    On Windows, icons use a transparent background with a colored
    bookmark ribbon.

    Args:
        state: One of 'normal', 'syncing', 'error'.
        dark_mode: Whether the OS is in dark mode.
        size: Icon size in pixels.

    Returns:
        QIcon ready for use as a system tray icon.
    """
    if _IS_LINUX:
        return _generate_linux_icon(state, dark_mode, size)
    return _generate_transparent_icon(state, dark_mode, size)


def _generate_linux_icon(state: str, dark_mode: bool, size: int) -> QIcon:
    """Generate an icon with opaque background for Linux system trays."""
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Background color based on state
    if state == "error":
        bg_color = QColor("#c62828")
    elif state == "syncing":
        bg_color = QColor("#1565c0")
    else:
        bg_color = QColor("#37474f")  # Blue-gray, neutral on light/dark panels

    # Draw rounded-rect background
    radius = size * 0.18
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(bg_color))
    painter.drawRoundedRect(1, 1, size - 2, size - 2, radius, radius)

    # Draw white bookmark ribbon on top
    margin = max(2, size // 4)
    w = size - 2 * margin
    h = size - 2 * margin
    x = margin
    y = margin

    path = QPainterPath()
    notch_depth = h * 0.2
    corner_radius = w * 0.15

    path.moveTo(x + corner_radius, y)
    path.lineTo(x + w - corner_radius, y)
    path.quadTo(x + w, y, x + w, y + corner_radius)
    path.lineTo(x + w, y + h - notch_depth)
    path.lineTo(x + w / 2, y + h - notch_depth * 2)
    path.lineTo(x, y + h - notch_depth)
    path.lineTo(x, y + corner_radius)
    path.quadTo(x, y, x + corner_radius, y)
    path.closeSubpath()

    painter.setBrush(QBrush(QColor("#ffffff")))
    painter.setPen(QPen(QColor("#e0e0e0"), max(1, size // 32)))
    painter.drawPath(path)

    painter.end()

    pixmap = QPixmap.fromImage(image)
    return QIcon(pixmap)


def _generate_transparent_icon(state: str, dark_mode: bool, size: int) -> QIcon:
    """Generate an icon with transparent background (Windows)."""
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

    path.moveTo(x + corner_radius, y)
    path.lineTo(x + w - corner_radius, y)
    path.quadTo(x + w, y, x + w, y + corner_radius)
    path.lineTo(x + w, y + h - notch_depth)
    path.lineTo(x + w / 2, y + h - notch_depth * 2)
    path.lineTo(x, y + h - notch_depth)
    path.lineTo(x, y + corner_radius)
    path.quadTo(x, y, x + corner_radius, y)
    path.closeSubpath()

    painter.setBrush(QBrush(fill_color))
    pen = QPen(border_color, max(1, size // 32))
    painter.setPen(pen)
    painter.drawPath(path)

    painter.end()

    pixmap = QPixmap.fromImage(image)
    return QIcon(pixmap)

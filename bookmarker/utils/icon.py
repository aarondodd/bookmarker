"""Icon generation for Bookmarker system tray."""

from PyQt6.QtCore import Qt, QRect, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QFont, QColor, QIcon, QPen, QBrush, QPainterPath


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

"""Icon generation for Bookmarker system tray."""

from pathlib import Path

from PyQt6.QtGui import QPixmap, QIcon

# Pre-rendered bookmark icon bundled with the package
_ICON_PATH = str(Path(__file__).parent / "bookmark.png")

_icon_cache = None


def generate_tray_icon(
    state: str = "normal",
    dark_mode: bool = False,
    size: int = 64,
) -> QIcon:
    """Return a bookmark ribbon icon for the system tray.

    Loads a pre-rendered PNG icon that works reliably across platforms.
    The state, dark_mode, and size parameters are accepted for API
    compatibility but do not affect the icon appearance.
    """
    global _icon_cache
    if _icon_cache is not None:
        return _icon_cache

    _icon_cache = QIcon(_ICON_PATH)
    return _icon_cache

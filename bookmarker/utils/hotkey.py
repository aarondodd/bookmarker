"""Global hotkey manager for Bookmarker.

Uses pynput for cross-platform global keyboard shortcuts.
"""

import logging

from PyQt6.QtCore import QTimer

log = logging.getLogger(__name__)

try:
    from pynput.keyboard import GlobalHotKeys

    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    log.warning("pynput not available - global hotkey feature disabled")


# Default hotkey in pynput format
DEFAULT_HOTKEY = "<ctrl>+<alt>+b"


def qt_to_pynput(qt_shortcut: str) -> str:
    """Convert a Qt key sequence string to pynput hotkey format.

    Qt format:  "Ctrl+Alt+B"
    pynput format: "<ctrl>+<alt>+b"
    """
    if not qt_shortcut:
        return ""

    parts = qt_shortcut.split("+")
    converted = []
    for part in parts:
        part = part.strip()
        lower = part.lower()
        if lower in ("ctrl", "alt", "shift", "meta", "cmd"):
            converted.append(f"<{lower}>")
        else:
            converted.append(lower)

    return "+".join(converted)


def pynput_to_qt(pynput_shortcut: str) -> str:
    """Convert a pynput hotkey string to Qt display format.

    pynput format: "<ctrl>+<alt>+b"
    Qt format:  "Ctrl+Alt+B"
    """
    if not pynput_shortcut:
        return ""

    parts = pynput_shortcut.split("+")
    converted = []
    for part in parts:
        part = part.strip()
        if part.startswith("<") and part.endswith(">"):
            name = part[1:-1]
            converted.append(name.capitalize())
        else:
            converted.append(part.upper())

    return "+".join(converted)


class GlobalHotkeyManager:
    """Manages a global hotkey that triggers a callback.

    The callback is marshalled to the Qt main thread via QTimer.singleShot.
    """

    def __init__(self, hotkey: str, callback):
        """Initialize the hotkey manager.

        Args:
            hotkey: Hotkey string in pynput format (e.g. "<ctrl>+<alt>+b").
            callback: Callable to invoke when the hotkey is pressed.
        """
        self._hotkey = hotkey
        self._callback = callback
        self._listener = None

    def start(self):
        """Start listening for the global hotkey."""
        if not PYNPUT_AVAILABLE:
            return

        self.stop()

        if not self._hotkey:
            return

        try:
            self._listener = GlobalHotKeys({
                self._hotkey: self._on_hotkey,
            })
            self._listener.daemon = True
            self._listener.start()
        except Exception:
            log.exception("Failed to start global hotkey listener")
            self._listener = None

    def stop(self):
        """Stop listening for the global hotkey."""
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def update_hotkey(self, new_hotkey: str):
        """Change the hotkey binding at runtime."""
        self._hotkey = new_hotkey
        self.start()

    def _on_hotkey(self):
        """Handle the hotkey press - marshal to Qt main thread."""
        QTimer.singleShot(0, self._callback)

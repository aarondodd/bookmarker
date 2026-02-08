"""Tests for global hotkey manager."""

from unittest.mock import patch, MagicMock

from bookmarker.utils.hotkey import (
    qt_to_pynput,
    pynput_to_qt,
    DEFAULT_HOTKEY,
    GlobalHotkeyManager,
)


class TestQtToPynput:
    def test_ctrl_alt_b(self):
        assert qt_to_pynput("Ctrl+Alt+B") == "<ctrl>+<alt>+b"

    def test_ctrl_shift_space(self):
        assert qt_to_pynput("Ctrl+Shift+F") == "<ctrl>+<shift>+f"

    def test_single_modifier_and_key(self):
        assert qt_to_pynput("Alt+X") == "<alt>+x"

    def test_empty_string(self):
        assert qt_to_pynput("") == ""

    def test_meta_key(self):
        assert qt_to_pynput("Meta+A") == "<meta>+a"


class TestPynputToQt:
    def test_ctrl_alt_b(self):
        assert pynput_to_qt("<ctrl>+<alt>+b") == "Ctrl+Alt+B"

    def test_ctrl_shift_f(self):
        assert pynput_to_qt("<ctrl>+<shift>+f") == "Ctrl+Shift+F"

    def test_single_modifier(self):
        assert pynput_to_qt("<alt>+x") == "Alt+X"

    def test_empty_string(self):
        assert pynput_to_qt("") == ""

    def test_roundtrip(self):
        original = "<ctrl>+<alt>+b"
        assert qt_to_pynput(pynput_to_qt(original)) == original


class TestDefaultHotkey:
    def test_default_is_ctrl_alt_b(self):
        assert DEFAULT_HOTKEY == "<ctrl>+<alt>+b"


class TestGlobalHotkeyManager:
    def test_start_stop_without_pynput(self):
        """Manager should work gracefully even if pynput is unavailable."""
        with patch("bookmarker.utils.hotkey.PYNPUT_AVAILABLE", False):
            callback = MagicMock()
            manager = GlobalHotkeyManager("<ctrl>+<alt>+b", callback)
            manager.start()  # Should not raise
            assert manager._listener is None
            manager.stop()  # Should not raise

    def test_update_hotkey(self):
        """update_hotkey should update the stored hotkey."""
        with patch("bookmarker.utils.hotkey.PYNPUT_AVAILABLE", False):
            callback = MagicMock()
            manager = GlobalHotkeyManager("<ctrl>+<alt>+b", callback)
            manager.update_hotkey("<ctrl>+<alt>+x")
            assert manager._hotkey == "<ctrl>+<alt>+x"

    def test_start_with_empty_hotkey(self):
        """Empty hotkey should not start a listener."""
        with patch("bookmarker.utils.hotkey.PYNPUT_AVAILABLE", True):
            callback = MagicMock()
            manager = GlobalHotkeyManager("", callback)
            manager.start()
            assert manager._listener is None

    @patch("bookmarker.utils.hotkey.PYNPUT_AVAILABLE", True)
    @patch("bookmarker.utils.hotkey.GlobalHotKeys")
    def test_start_creates_listener(self, mock_global_hotkeys):
        """start() should create and start a GlobalHotKeys listener."""
        mock_listener = MagicMock()
        mock_global_hotkeys.return_value = mock_listener

        callback = MagicMock()
        manager = GlobalHotkeyManager("<ctrl>+<alt>+b", callback)
        manager.start()

        mock_global_hotkeys.assert_called_once()
        mock_listener.start.assert_called_once()
        assert manager._listener is mock_listener

    @patch("bookmarker.utils.hotkey.PYNPUT_AVAILABLE", True)
    @patch("bookmarker.utils.hotkey.GlobalHotKeys")
    def test_stop_stops_listener(self, mock_global_hotkeys):
        """stop() should stop the running listener."""
        mock_listener = MagicMock()
        mock_global_hotkeys.return_value = mock_listener

        callback = MagicMock()
        manager = GlobalHotkeyManager("<ctrl>+<alt>+b", callback)
        manager.start()
        manager.stop()

        mock_listener.stop.assert_called_once()
        assert manager._listener is None

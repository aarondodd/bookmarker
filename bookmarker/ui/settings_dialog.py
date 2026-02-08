"""Application settings dialog."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QPushButton, QDialogButtonBox, QGroupBox, QFormLayout,
    QKeySequenceEdit,
)
from PyQt6.QtGui import QKeySequence

from ..utils.config import (
    get_ui_config, set_ui_config, get_sync_config, set_sync_config,
    get_hotkey_config, set_hotkey_config,
)
from ..utils.hotkey import DEFAULT_HOTKEY, qt_to_pynput, pynput_to_qt


class SettingsDialog(QDialog):
    """Dialog for configuring application settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)

        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # UI Settings
        ui_group = QGroupBox("Appearance")
        ui_layout = QFormLayout(ui_group)

        self._dark_mode_cb = QCheckBox("Enable dark mode")
        ui_layout.addRow(self._dark_mode_cb)

        layout.addWidget(ui_group)

        # Sync Settings
        sync_group = QGroupBox("Sync")
        sync_layout = QFormLayout(sync_group)

        self._debug_mode_cb = QCheckBox("Debug mode (confirm each sync change)")
        sync_layout.addRow(self._debug_mode_cb)

        layout.addWidget(sync_group)

        # Hotkey Settings
        hotkey_group = QGroupBox("Global Hotkey")
        hotkey_layout = QFormLayout(hotkey_group)

        self._hotkey_enabled_cb = QCheckBox("Enable global hotkey for Quick Launch")
        hotkey_layout.addRow(self._hotkey_enabled_cb)

        self._hotkey_edit = QKeySequenceEdit()
        self._hotkey_edit.setToolTip("Click and press the desired key combination")
        hotkey_layout.addRow("Shortcut:", self._hotkey_edit)

        self._hotkey_enabled_cb.toggled.connect(self._hotkey_edit.setEnabled)

        layout.addWidget(hotkey_group)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_settings(self):
        ui = get_ui_config()
        self._dark_mode_cb.setChecked(ui.get("dark_mode", False))

        sync = get_sync_config()
        self._debug_mode_cb.setChecked(sync.get("debug_mode", False))

        hotkey = get_hotkey_config()
        self._hotkey_enabled_cb.setChecked(hotkey.get("enabled", True))
        shortcut = hotkey.get("shortcut", DEFAULT_HOTKEY)
        qt_shortcut = pynput_to_qt(shortcut)
        self._hotkey_edit.setKeySequence(QKeySequence(qt_shortcut))
        self._hotkey_edit.setEnabled(self._hotkey_enabled_cb.isChecked())

    def _save_and_accept(self):
        set_ui_config({"dark_mode": self._dark_mode_cb.isChecked()})
        set_sync_config({"debug_mode": self._debug_mode_cb.isChecked()})

        qt_seq = self._hotkey_edit.keySequence().toString()
        pynput_shortcut = qt_to_pynput(qt_seq) if qt_seq else DEFAULT_HOTKEY
        set_hotkey_config({
            "enabled": self._hotkey_enabled_cb.isChecked(),
            "shortcut": pynput_shortcut,
        })

        self.accept()

    def is_dark_mode(self) -> bool:
        return self._dark_mode_cb.isChecked()

    def is_debug_mode(self) -> bool:
        return self._debug_mode_cb.isChecked()

    def is_hotkey_enabled(self) -> bool:
        return self._hotkey_enabled_cb.isChecked()

    def hotkey_shortcut(self) -> str:
        """Return the hotkey shortcut in pynput format."""
        qt_seq = self._hotkey_edit.keySequence().toString()
        return qt_to_pynput(qt_seq) if qt_seq else DEFAULT_HOTKEY

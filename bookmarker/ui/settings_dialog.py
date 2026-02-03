"""Application settings dialog."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QPushButton, QDialogButtonBox, QGroupBox, QFormLayout,
)

from ..utils.config import get_ui_config, set_ui_config, get_sync_config, set_sync_config


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

    def _save_and_accept(self):
        set_ui_config({"dark_mode": self._dark_mode_cb.isChecked()})
        set_sync_config({"debug_mode": self._debug_mode_cb.isChecked()})
        self.accept()

    def is_dark_mode(self) -> bool:
        return self._dark_mode_cb.isChecked()

    def is_debug_mode(self) -> bool:
        return self._debug_mode_cb.isChecked()

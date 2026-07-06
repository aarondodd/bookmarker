"""Application settings dialog.

Also hosts Browser Sync setup (extract the extension + register the native host)
and its auto-sync preferences -- these live here rather than in the tray menu, so
the tray only carries actions, not configuration.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QPushButton, QDialogButtonBox, QGroupBox, QFormLayout,
    QKeySequenceEdit, QSpinBox, QPlainTextEdit, QMessageBox,
)
from PyQt6.QtGui import QKeySequence

from ..utils.config import (
    get_ui_config, set_ui_config, get_sync_config, set_sync_config,
    get_hotkey_config, set_hotkey_config,
    get_automation_config, set_automation_config,
)
from ..utils.hotkey import DEFAULT_HOTKEY, qt_to_pynput, pynput_to_qt
from ..automation import installer


class SettingsDialog(QDialog):
    """Dialog for configuring application settings."""

    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("Settings")
        self.setMinimumWidth(460)

        self._setup_ui()
        self._load_settings()

        if controller is not None:
            controller.status.connect(self._on_sync_status)
            controller.connection_changed.connect(self._on_sync_connection)
            self._on_sync_connection(controller.is_connected)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Appearance
        ui_group = QGroupBox("Appearance")
        ui_layout = QFormLayout(ui_group)
        self._dark_mode_cb = QCheckBox("Enable dark mode")
        ui_layout.addRow(self._dark_mode_cb)
        layout.addWidget(ui_group)

        # Manual sync (file-based)
        sync_group = QGroupBox("Manual sync (browser closed)")
        sync_layout = QFormLayout(sync_group)
        self._debug_mode_cb = QCheckBox("Debug mode (confirm each sync change)")
        sync_layout.addRow(self._debug_mode_cb)
        layout.addWidget(sync_group)

        # Global hotkey
        hotkey_group = QGroupBox("Global Hotkey")
        hotkey_layout = QFormLayout(hotkey_group)
        self._hotkey_enabled_cb = QCheckBox("Enable global hotkey for Quick Launch")
        hotkey_layout.addRow(self._hotkey_enabled_cb)
        self._hotkey_edit = QKeySequenceEdit()
        self._hotkey_edit.setToolTip("Click and press the desired key combination")
        hotkey_layout.addRow("Shortcut:", self._hotkey_edit)
        self._hotkey_enabled_cb.toggled.connect(self._hotkey_edit.setEnabled)
        layout.addWidget(hotkey_group)

        # Browser Sync (live extension)
        layout.addWidget(self._build_browser_sync_group())

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------ browser sync

    def _build_browser_sync_group(self) -> QGroupBox:
        group = QGroupBox("Browser Sync (live extension)")
        v = QVBoxLayout(group)

        self._install_label = QLabel()
        self._install_label.setWordWrap(True)
        v.addWidget(self._install_label)

        btn_row = QHBoxLayout()
        self._setup_btn = QPushButton("Set Up / Reinstall")
        self._setup_btn.clicked.connect(self._do_setup)
        btn_row.addWidget(self._setup_btn)
        self._remove_btn = QPushButton("Remove Registration")
        self._remove_btn.clicked.connect(self._do_remove)
        btn_row.addWidget(self._remove_btn)
        v.addLayout(btn_row)

        self._instructions = QPlainTextEdit()
        self._instructions.setReadOnly(True)
        self._instructions.setFixedHeight(92)
        v.addWidget(self._instructions)

        self._conn_label = QLabel("Browser: not connected")
        v.addWidget(self._conn_label)

        self._replace_btn = QPushButton("Replace Browser with Bookmarker's")
        self._replace_btn.clicked.connect(self._do_replace)
        v.addWidget(self._replace_btn)

        auto_form = QFormLayout()
        self._auto_cb = QCheckBox("Keep the browser in sync automatically")
        auto_form.addRow(self._auto_cb)
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 240)
        self._interval_spin.setSuffix(" min")
        auto_form.addRow("Interval:", self._interval_spin)
        v.addLayout(auto_form)

        self._sync_status_label = QLabel("")
        self._sync_status_label.setWordWrap(True)
        v.addWidget(self._sync_status_label)

        self._refresh_install_state()
        return group

    def _refresh_install_state(self):
        state = installer.installation_state()
        ext = "yes" if state["extension_extracted"] else "no"
        host = "yes" if state["native_manifest_written"] else "no"
        self._install_label.setText(
            f"Extension extracted: {ext}    Native host registered: {host}\n"
            f"Extension ID: {state['extension_id']}"
        )
        self._instructions.setPlainText(
            "To finish setup, load the extension once in your browser:\n"
            "1. Open chrome://extensions (or edge://extensions)\n"
            "2. Enable Developer mode\n"
            "3. Click 'Load unpacked' and select:\n"
            f"   {state['extension_path']}"
        )

    def _do_setup(self):
        try:
            installer.install()
        except Exception as exc:  # noqa: BLE001 -- surface any install failure
            QMessageBox.warning(self, "Setup failed", str(exc))
            return
        self._refresh_install_state()
        QMessageBox.information(
            self, "Setup complete",
            "Extension extracted and native host registered.\n\n"
            "Now load the unpacked extension in your browser (instructions shown).",
        )

    def _do_remove(self):
        installer.uninstall()
        self._refresh_install_state()

    def _do_replace(self):
        if self._controller is None:
            return
        if QMessageBox.question(
            self, "Replace browser bookmarks?",
            "This wipes the connected browser's bookmarks and recreates them "
            "from Bookmarker's store. Continue?",
        ) == QMessageBox.StandardButton.Yes:
            self._controller.replace()

    def _on_sync_status(self, text: str):
        self._sync_status_label.setText(text)

    def _on_sync_connection(self, connected: bool):
        self._conn_label.setText(
            "Browser: connected" if connected else "Browser: not connected"
        )
        self._replace_btn.setEnabled(connected)

    # ------------------------------------------------------------------ load/save

    def _load_settings(self):
        ui = get_ui_config()
        self._dark_mode_cb.setChecked(ui.get("dark_mode", False))

        sync = get_sync_config()
        self._debug_mode_cb.setChecked(sync.get("debug_mode", False))

        hotkey = get_hotkey_config()
        self._hotkey_enabled_cb.setChecked(hotkey.get("enabled", True))
        shortcut = hotkey.get("shortcut", DEFAULT_HOTKEY)
        self._hotkey_edit.setKeySequence(QKeySequence(pynput_to_qt(shortcut)))
        self._hotkey_edit.setEnabled(self._hotkey_enabled_cb.isChecked())

        auto = get_automation_config()
        self._auto_cb.setChecked(bool(auto.get("auto_sync", False)))
        self._interval_spin.setValue(int(auto.get("interval_minutes", 15)))

    def _save_and_accept(self):
        set_ui_config({"dark_mode": self._dark_mode_cb.isChecked()})
        set_sync_config({"debug_mode": self._debug_mode_cb.isChecked()})

        qt_seq = self._hotkey_edit.keySequence().toString()
        pynput_shortcut = qt_to_pynput(qt_seq) if qt_seq else DEFAULT_HOTKEY
        set_hotkey_config({
            "enabled": self._hotkey_enabled_cb.isChecked(),
            "shortcut": pynput_shortcut,
        })

        auto = get_automation_config()
        auto["auto_sync"] = self._auto_cb.isChecked()
        auto["interval_minutes"] = self._interval_spin.value()
        set_automation_config(auto)

        self.accept()

    # ------------------------------------------------------------------ getters

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

    def is_auto_sync(self) -> bool:
        return self._auto_cb.isChecked()

    def auto_sync_interval(self) -> int:
        return self._interval_spin.value()

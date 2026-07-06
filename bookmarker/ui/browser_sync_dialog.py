"""Browser Sync setup + control dialog.

Surfaces the guided-manual install (extract extension + register native host),
the live connection status, the replace/sync actions, and the auto-sync toggle.
The heavy lifting lives in ``automation.installer`` and ``automation.controller``.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QPushButton,
    QCheckBox, QSpinBox, QFormLayout, QPlainTextEdit, QMessageBox,
)

from ..automation import installer
from ..utils.config import get_automation_config, set_automation_config


class BrowserSyncDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("Browser Sync")
        self.setMinimumWidth(480)
        self._setup_ui()
        self._refresh_install_state()
        self._load_settings()

        if controller is not None:
            controller.status.connect(self._on_status)
            controller.connection_changed.connect(self._on_connection)
            self._on_connection(controller.is_connected)

    # ------------------------------------------------------------------ ui

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Setup ---
        setup_group = QGroupBox("Extension setup")
        setup_layout = QVBoxLayout(setup_group)
        self._install_label = QLabel()
        self._install_label.setWordWrap(True)
        setup_layout.addWidget(self._install_label)

        btn_row = QHBoxLayout()
        self._setup_btn = QPushButton("Set Up / Reinstall")
        self._setup_btn.clicked.connect(self._do_setup)
        btn_row.addWidget(self._setup_btn)
        self._remove_btn = QPushButton("Remove Registration")
        self._remove_btn.clicked.connect(self._do_remove)
        btn_row.addWidget(self._remove_btn)
        setup_layout.addLayout(btn_row)

        self._instructions = QPlainTextEdit()
        self._instructions.setReadOnly(True)
        self._instructions.setFixedHeight(96)
        setup_layout.addWidget(self._instructions)
        layout.addWidget(setup_group)

        # --- Connection + actions ---
        conn_group = QGroupBox("Sync")
        conn_layout = QVBoxLayout(conn_group)
        self._conn_label = QLabel("Browser: not connected")
        conn_layout.addWidget(self._conn_label)

        action_row = QHBoxLayout()
        self._sync_btn = QPushButton("Sync Now")
        self._sync_btn.clicked.connect(self._do_sync)
        action_row.addWidget(self._sync_btn)
        self._replace_btn = QPushButton("Replace Browser with Bookmarker's")
        self._replace_btn.clicked.connect(self._do_replace)
        action_row.addWidget(self._replace_btn)
        conn_layout.addLayout(action_row)
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        conn_layout.addWidget(self._status_label)
        layout.addWidget(conn_group)

        # --- Auto sync ---
        auto_group = QGroupBox("Automatic sync")
        auto_layout = QFormLayout(auto_group)
        self._auto_cb = QCheckBox("Keep the browser in sync automatically")
        auto_layout.addRow(self._auto_cb)
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 240)
        self._interval_spin.setSuffix(" min")
        auto_layout.addRow("Interval:", self._interval_spin)
        self._auto_cb.toggled.connect(self._save_settings)
        self._interval_spin.valueChanged.connect(self._save_settings)
        layout.addWidget(auto_group)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    # ------------------------------------------------------------------ state

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

    def _load_settings(self):
        cfg = get_automation_config()
        self._auto_cb.setChecked(bool(cfg.get("auto_sync", False)))
        self._interval_spin.setValue(int(cfg.get("interval_minutes", 15)))

    def _save_settings(self):
        cfg = get_automation_config()
        cfg["auto_sync"] = self._auto_cb.isChecked()
        cfg["interval_minutes"] = self._interval_spin.value()
        set_automation_config(cfg)
        if self._controller is not None:
            self._controller.set_auto_sync(cfg["auto_sync"], cfg["interval_minutes"])

    # ------------------------------------------------------------------ actions

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

    def _do_sync(self):
        if self._controller and not self._controller.sync_now():
            self._status_label.setText("No browser connected.")

    def _do_replace(self):
        if not self._controller:
            return
        if QMessageBox.question(
            self, "Replace browser bookmarks?",
            "This wipes the connected browser's bookmarks and recreates them "
            "from Bookmarker's store. Continue?",
        ) == QMessageBox.StandardButton.Yes:
            self._controller.replace()

    # ------------------------------------------------------------------ signals

    def _on_status(self, text: str):
        self._status_label.setText(text)

    def _on_connection(self, connected: bool):
        self._conn_label.setText(
            "Browser: connected" if connected else "Browser: not connected"
        )
        self._sync_btn.setEnabled(connected)
        self._replace_btn.setEnabled(connected)

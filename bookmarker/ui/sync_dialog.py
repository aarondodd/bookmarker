"""Sync/import/push progress dialog."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QTextEdit,
    QPushButton, QDialogButtonBox,
)


class SyncProgressDialog(QDialog):
    """Shows progress for import, push, or sync operations."""

    def __init__(self, title: str = "Operation in Progress", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.setMinimumHeight(250)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self._status_label = QLabel("Starting...")
        layout.addWidget(self._status_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # Indeterminate
        layout.addWidget(self._progress_bar)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        layout.addWidget(self._log)

        self._close_btn = QPushButton("Close")
        self._close_btn.setEnabled(False)
        self._close_btn.clicked.connect(self.accept)
        layout.addWidget(self._close_btn)

    def set_status(self, message: str):
        """Update the status label."""
        self._status_label.setText(message)
        self._log.append(message)

    def set_progress(self, value: int, maximum: int):
        """Set determinate progress."""
        self._progress_bar.setRange(0, maximum)
        self._progress_bar.setValue(value)

    def finish(self, message: str):
        """Mark the operation as complete."""
        self._status_label.setText(message)
        self._log.append(f"\n{message}")
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(1)
        self._close_btn.setEnabled(True)

"""Debug confirmation dialog for sync operations."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
)

from ..operations.sync import SyncAction


class DebugConfirmDialog(QDialog):
    """Shows a proposed sync change with Apply/Skip/Apply All buttons."""

    APPLY = 1
    SKIP = 2
    APPLY_ALL = 3

    def __init__(self, action: SyncAction, current: int, total: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Sync Change {current}/{total}")
        self.setMinimumWidth(450)
        self.result_action = self.SKIP

        self._setup_ui(action, current, total)

    def _setup_ui(self, action, current, total):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel(f"<b>Change {current} of {total}</b>")
        layout.addWidget(header)

        # Action type
        action_label = QLabel(f"<b>Action:</b> {action.action.value}")
        layout.addWidget(action_label)

        # Description
        desc = QTextEdit()
        desc.setReadOnly(True)
        desc.setMaximumHeight(80)
        details = (
            f"Title: {action.bookmark.title}\n"
            f"URL: {action.bookmark.url}\n"
            f"Root: {action.root_name}\n"
            f"Path: {action.parent_title or '(root)'}\n"
            f"\n{action.description}"
        )
        desc.setPlainText(details)
        layout.addWidget(desc)

        # Buttons
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(apply_btn)

        skip_btn = QPushButton("Skip")
        skip_btn.clicked.connect(self._on_skip)
        btn_layout.addWidget(skip_btn)

        apply_all_btn = QPushButton("Apply All Remaining")
        apply_all_btn.clicked.connect(self._on_apply_all)
        btn_layout.addWidget(apply_all_btn)

        layout.addLayout(btn_layout)

    def _on_apply(self):
        self.result_action = self.APPLY
        self.accept()

    def _on_skip(self):
        self.result_action = self.SKIP
        self.accept()

    def _on_apply_all(self):
        self.result_action = self.APPLY_ALL
        self.accept()

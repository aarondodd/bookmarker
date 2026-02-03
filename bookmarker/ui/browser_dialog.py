"""Browser selection dialog for import/push operations."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QPushButton, QDialogButtonBox, QGroupBox,
)

from ..operations.browser_detect import detect_browsers, BrowserInfo


class BrowserSelectionDialog(QDialog):
    """Dialog for selecting browsers for import or push operations."""

    def __init__(self, title: str = "Select Browsers",
                 operation: str = "import", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(350)
        self.operation = operation
        self._checkboxes = {}

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        label = QLabel(f"Select browsers to {self.operation}:")
        layout.addWidget(label)

        group = QGroupBox("Browsers")
        group_layout = QVBoxLayout(group)

        browsers = detect_browsers()
        for browser in browsers:
            row = QHBoxLayout()
            cb = QCheckBox(browser.display_name)
            cb.setEnabled(browser.installed)
            self._checkboxes[browser.name] = cb
            row.addWidget(cb)

            if not browser.installed:
                status = QLabel("(not installed)")
                status.setStyleSheet("color: gray;")
                row.addWidget(status)
            elif browser.running and self.operation == "push":
                status = QLabel("(running - close first)")
                status.setStyleSheet("color: orange;")
                row.addWidget(status)

            row.addStretch()
            group_layout.addLayout(row)

        layout.addWidget(group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_browsers(self):
        """Return list of selected browser names."""
        return [name for name, cb in self._checkboxes.items() if cb.isChecked()]

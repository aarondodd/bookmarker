"""Dialog for selecting import mode (merge or overwrite)."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QRadioButton, QButtonGroup,
    QDialogButtonBox, QGroupBox,
)

from ..operations.store_export import ImportMode


class ImportModeDialog(QDialog):
    """Dialog for selecting between merge and overwrite import modes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Mode")
        self.setMinimumWidth(400)
        self._selected_mode = ImportMode.MERGE

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        label = QLabel("How would you like to import the bookmarks?")
        layout.addWidget(label)

        group = QGroupBox("Import Mode")
        group_layout = QVBoxLayout(group)

        self._button_group = QButtonGroup(self)

        # Merge option (default)
        self._merge_radio = QRadioButton("Merge")
        self._merge_radio.setChecked(True)
        merge_desc = QLabel(
            "Add new bookmarks to your existing collection.\n"
            "Duplicates will be detected and you can resolve conflicts."
        )
        merge_desc.setStyleSheet("color: gray; margin-left: 20px; margin-bottom: 10px;")
        merge_desc.setWordWrap(True)
        self._button_group.addButton(self._merge_radio, 0)
        group_layout.addWidget(self._merge_radio)
        group_layout.addWidget(merge_desc)

        # Overwrite option
        self._overwrite_radio = QRadioButton("Overwrite")
        overwrite_desc = QLabel(
            "Replace all existing bookmarks with the imported file.\n"
            "Warning: This will delete your current bookmarks!"
        )
        overwrite_desc.setStyleSheet("color: gray; margin-left: 20px;")
        overwrite_desc.setWordWrap(True)
        self._button_group.addButton(self._overwrite_radio, 1)
        group_layout.addWidget(self._overwrite_radio)
        group_layout.addWidget(overwrite_desc)

        layout.addWidget(group)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_mode(self) -> ImportMode:
        """Return the selected import mode."""
        if self._overwrite_radio.isChecked():
            return ImportMode.OVERWRITE
        return ImportMode.MERGE

"""Dialog for previewing import and resolving conflicts."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, QButtonGroup,
    QDialogButtonBox, QTabWidget, QWidget, QTreeWidget, QTreeWidgetItem,
    QScrollArea, QFrame, QGroupBox,
)

from ..operations.store_export import ImportPreview, MergeConflict, ConflictResolution


class ImportPreviewDialog(QDialog):
    """Dialog for previewing import changes and resolving conflicts."""

    def __init__(self, preview: ImportPreview, parent=None):
        super().__init__(parent)
        self.preview = preview
        self.setWindowTitle("Import Preview")
        self.setMinimumSize(600, 450)

        self._conflict_groups = []  # List of (conflict, button_group)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Summary
        add_count = len(self.preview.bookmarks_to_add)
        conflict_count = len(self.preview.conflicts)

        summary = QLabel(
            f"Found {add_count} new bookmark(s) to add"
            + (f" and {conflict_count} conflict(s) to resolve." if conflict_count else ".")
        )
        summary.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(summary)

        # Tab widget
        tabs = QTabWidget()

        # Add tab - tree of bookmarks to add
        add_widget = self._create_add_tab()
        tabs.addTab(add_widget, f"To Add ({add_count})")

        # Conflicts tab
        if conflict_count > 0:
            conflicts_widget = self._create_conflicts_tab()
            tabs.addTab(conflicts_widget, f"Conflicts ({conflict_count})")
            tabs.setCurrentIndex(1)  # Show conflicts first if any

        layout.addWidget(tabs)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Import")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _create_add_tab(self) -> QWidget:
        """Create the tab showing bookmarks to be added."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        if not self.preview.bookmarks_to_add:
            label = QLabel("No new bookmarks to add.")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            return widget

        tree = QTreeWidget()
        tree.setHeaderLabels(["Title", "URL", "Folder"])
        tree.setColumnWidth(0, 200)
        tree.setColumnWidth(1, 250)

        # Group by folder path
        by_folder = {}
        for bm, folder_path in self.preview.bookmarks_to_add:
            if folder_path not in by_folder:
                by_folder[folder_path] = []
            by_folder[folder_path].append(bm)

        for folder_path in sorted(by_folder.keys()):
            folder_item = QTreeWidgetItem([folder_path, "", ""])
            folder_item.setFlags(folder_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            tree.addTopLevelItem(folder_item)

            for bm in by_folder[folder_path]:
                bm_item = QTreeWidgetItem(["", bm.title, bm.url])
                folder_item.addChild(bm_item)

            folder_item.setExpanded(True)

        layout.addWidget(tree)
        return widget

    def _create_conflicts_tab(self) -> QWidget:
        """Create the tab for conflict resolution."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        if not self.preview.conflicts:
            label = QLabel("No conflicts to resolve.")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            return widget

        instruction = QLabel(
            "The following bookmarks have the same URL in the same folder "
            "but different titles. Choose which version to keep:"
        )
        instruction.setWordWrap(True)
        layout.addWidget(instruction)

        # Scroll area for conflicts
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        for i, conflict in enumerate(self.preview.conflicts):
            group = self._create_conflict_widget(i, conflict)
            scroll_layout.addWidget(group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        return widget

    def _create_conflict_widget(self, index: int, conflict: MergeConflict) -> QGroupBox:
        """Create a widget for a single conflict resolution."""
        group = QGroupBox(f"Conflict {index + 1}: {conflict.folder_path}")
        layout = QVBoxLayout(group)

        # URL (shared)
        url_label = QLabel(f"URL: {conflict.existing_bookmark.url}")
        url_label.setStyleSheet("color: gray;")
        url_label.setWordWrap(True)
        layout.addWidget(url_label)

        button_group = QButtonGroup(self)

        # Existing option
        existing_row = QHBoxLayout()
        existing_radio = QRadioButton("Keep existing:")
        existing_radio.setChecked(True)  # Default to keep existing
        button_group.addButton(existing_radio, 0)
        existing_title = QLabel(f'"{conflict.existing_bookmark.title}"')
        existing_title.setStyleSheet("font-style: italic;")
        existing_row.addWidget(existing_radio)
        existing_row.addWidget(existing_title)
        existing_row.addStretch()
        layout.addLayout(existing_row)

        # Imported option
        imported_row = QHBoxLayout()
        imported_radio = QRadioButton("Use imported:")
        button_group.addButton(imported_radio, 1)
        imported_title = QLabel(f'"{conflict.imported_bookmark.title}"')
        imported_title.setStyleSheet("font-style: italic;")
        imported_row.addWidget(imported_radio)
        imported_row.addWidget(imported_title)
        imported_row.addStretch()
        layout.addLayout(imported_row)

        self._conflict_groups.append((conflict, button_group))

        return group

    def _on_accept(self):
        """Apply conflict resolutions before accepting."""
        for conflict, button_group in self._conflict_groups:
            if button_group.checkedId() == 0:
                conflict.resolution = ConflictResolution.KEEP_EXISTING
            else:
                conflict.resolution = ConflictResolution.USE_IMPORTED

        self.accept()

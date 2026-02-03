"""Bookmark Editor - main editing window with tree view and edit panel."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFormLayout,
    QTreeWidget, QTreeWidgetItem, QLineEdit, QComboBox,
    QPushButton, QToolBar, QSplitter, QLabel, QMessageBox,
)

from ..models.bookmark import Bookmark, BookmarkType, BookmarkStore


class BookmarkEditorWindow(QMainWindow):
    """Non-modal window for editing bookmarks."""

    store_changed = pyqtSignal()

    def __init__(self, store: BookmarkStore, parent=None):
        super().__init__(parent)
        self.store = store
        self._current_item = None

        self.setWindowTitle("Bookmark Editor")
        self.setMinimumSize(800, 500)

        self._setup_toolbar()
        self._setup_ui()
        self._populate_tree()

    def _setup_toolbar(self):
        toolbar = QToolBar("Actions")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._add_bookmark_btn = toolbar.addAction("+ Bookmark")
        self._add_bookmark_btn.triggered.connect(self._add_bookmark)

        self._add_folder_btn = toolbar.addAction("+ Folder")
        self._add_folder_btn.triggered.connect(self._add_folder)

        self._delete_btn = toolbar.addAction("Delete")
        self._delete_btn.triggered.connect(self._delete_selected)

        toolbar.addSeparator()

        self._move_up_btn = toolbar.addAction("Move Up")
        self._move_up_btn.triggered.connect(self._move_up)

        self._move_down_btn = toolbar.addAction("Move Down")
        self._move_down_btn.triggered.connect(self._move_down)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: tree view
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self._tree.currentItemChanged.connect(self._on_selection_changed)
        splitter.addWidget(self._tree)

        # Right: edit panel
        edit_panel = QWidget()
        edit_layout = QVBoxLayout(edit_panel)

        form = QFormLayout()

        self._title_edit = QLineEdit()
        form.addRow("Title:", self._title_edit)

        self._url_edit = QLineEdit()
        form.addRow("URL:", self._url_edit)

        self._folder_combo = QComboBox()
        form.addRow("Folder:", self._folder_combo)

        self._browser_combo = QComboBox()
        self._browser_combo.addItems(["Any browser", "chrome", "edge", "firefox"])
        form.addRow("Open in:", self._browser_combo)

        edit_layout.addLayout(form)

        self._save_btn = QPushButton("Save Changes")
        self._save_btn.clicked.connect(self._save_changes)
        edit_layout.addWidget(self._save_btn)

        edit_layout.addStretch()
        splitter.addWidget(edit_panel)

        # 40/60 split
        splitter.setSizes([320, 480])

        layout = QHBoxLayout(central)
        layout.addWidget(splitter)

    def _populate_tree(self):
        """Populate the tree widget from the store."""
        self._tree.clear()
        self._update_folder_combo()

        for root_name, root_bm in self.store.roots.items():
            root_item = QTreeWidgetItem(self._tree, [root_bm.title])
            root_item.setData(0, Qt.ItemDataRole.UserRole, root_bm.id)
            root_item.setFlags(
                root_item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled
            )
            self._add_children_to_tree(root_item, root_bm)
            root_item.setExpanded(True)

    def _add_children_to_tree(self, parent_item: QTreeWidgetItem,
                              parent_bm: Bookmark):
        """Recursively add bookmark children to the tree."""
        for child in parent_bm.children:
            if child.type == BookmarkType.FOLDER:
                display = f"[F] {child.title}"
            else:
                display = child.title
            item = QTreeWidgetItem(parent_item, [display])
            item.setData(0, Qt.ItemDataRole.UserRole, child.id)
            if child.type == BookmarkType.FOLDER:
                self._add_children_to_tree(item, child)
                item.setExpanded(True)

    def _update_folder_combo(self):
        """Update the folder dropdown with all available folders."""
        self._folder_combo.clear()
        for root_name, root_bm in self.store.roots.items():
            self._folder_combo.addItem(root_bm.title, root_bm.id)
            self._add_folder_combo_items(root_bm, "  ")

    def _add_folder_combo_items(self, parent: Bookmark, prefix: str):
        for child in parent.children:
            if child.type == BookmarkType.FOLDER:
                self._folder_combo.addItem(f"{prefix}{child.title}", child.id)
                self._add_folder_combo_items(child, prefix + "  ")

    def _on_selection_changed(self, current, previous):
        """Handle tree selection change - populate edit panel."""
        if current is None:
            return

        bm_id = current.data(0, Qt.ItemDataRole.UserRole)
        if bm_id is None:
            return

        bm = self.store.find_by_id(bm_id)
        if bm is None:
            return

        self._current_item = bm
        self._title_edit.setText(bm.title)
        self._url_edit.setText(bm.url)
        self._url_edit.setEnabled(bm.type == BookmarkType.URL)

        # Set folder combo to parent
        if bm.parent_id:
            idx = self._folder_combo.findData(bm.parent_id)
            if idx >= 0:
                self._folder_combo.setCurrentIndex(idx)

        # Set browser preference
        if bm.preferred_browser:
            idx = self._browser_combo.findText(bm.preferred_browser)
            if idx >= 0:
                self._browser_combo.setCurrentIndex(idx)
        else:
            self._browser_combo.setCurrentIndex(0)

    def _save_changes(self):
        """Save edits to the current bookmark."""
        if self._current_item is None:
            return

        bm = self._current_item
        bm.title = self._title_edit.text()
        if bm.type == BookmarkType.URL:
            bm.url = self._url_edit.text()

        browser = self._browser_combo.currentText()
        bm.preferred_browser = None if browser == "Any browser" else browser

        # Handle folder move
        new_parent_id = self._folder_combo.currentData()
        if new_parent_id and new_parent_id != bm.parent_id:
            self.store.move(bm.id, new_parent_id)

        from datetime import datetime
        bm.date_modified = datetime.now().isoformat()

        self.store.save()
        self._populate_tree()
        self.store_changed.emit()

    def _add_bookmark(self):
        """Add a new bookmark."""
        self.add_bookmark_with_url("https://")

    def add_bookmark_with_url(self, url: str, title: str = "New Bookmark"):
        """Add a new bookmark with a specific URL and optionally select it for editing.

        Args:
            url: The URL for the new bookmark.
            title: The title for the new bookmark.
        """
        parent_id = self._folder_combo.currentData()
        bm = Bookmark(title=title, url=url, type=BookmarkType.URL)
        self.store.add(bm, parent_id=parent_id)
        self.store.save()
        self._populate_tree()
        self.store_changed.emit()

        # Select the newly added bookmark in the tree and focus the title field
        self._select_bookmark_by_id(bm.id)
        self._title_edit.setFocus()
        self._title_edit.selectAll()

    def _select_bookmark_by_id(self, bookmark_id: str):
        """Select a bookmark in the tree by its ID."""
        def find_item(parent_item, target_id):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole) == target_id:
                    return child
                found = find_item(child, target_id)
                if found:
                    return found
            return None

        for i in range(self._tree.topLevelItemCount()):
            top_item = self._tree.topLevelItem(i)
            if top_item.data(0, Qt.ItemDataRole.UserRole) == bookmark_id:
                self._tree.setCurrentItem(top_item)
                return
            found = find_item(top_item, bookmark_id)
            if found:
                self._tree.setCurrentItem(found)
                return

    def _add_folder(self):
        """Add a new folder."""
        parent_id = self._folder_combo.currentData()
        folder = Bookmark(title="New Folder", type=BookmarkType.FOLDER)
        self.store.add(folder, parent_id=parent_id)
        self.store.save()
        self._populate_tree()
        self.store_changed.emit()

    def _delete_selected(self):
        """Delete the selected bookmark."""
        item = self._tree.currentItem()
        if item is None:
            return

        bm_id = item.data(0, Qt.ItemDataRole.UserRole)
        bm = self.store.find_by_id(bm_id)
        if bm is None:
            return

        # Don't delete root folders
        if bm_id in [r.id for r in self.store.roots.values()]:
            QMessageBox.warning(self, "Cannot Delete", "Cannot delete root folders.")
            return

        reply = QMessageBox.question(
            self, "Delete Bookmark",
            f"Delete '{bm.title}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.store.remove(bm_id)
            self.store.save()
            self._populate_tree()
            self._current_item = None
            self.store_changed.emit()

    def _move_up(self):
        """Move the selected bookmark up in its parent."""
        self._move_selected(-1)

    def _move_down(self):
        """Move the selected bookmark down in its parent."""
        self._move_selected(1)

    def _move_selected(self, direction: int):
        """Move the selected bookmark by the given direction (-1 up, +1 down)."""
        item = self._tree.currentItem()
        if item is None:
            return

        bm_id = item.data(0, Qt.ItemDataRole.UserRole)
        bm = self.store.find_by_id(bm_id)
        if bm is None or bm.parent_id is None:
            return

        parent = self.store.find_by_id(bm.parent_id)
        if parent is None:
            return

        idx = next((i for i, c in enumerate(parent.children) if c.id == bm_id), -1)
        if idx < 0:
            return

        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(parent.children):
            return

        # Swap
        parent.children[idx], parent.children[new_idx] = \
            parent.children[new_idx], parent.children[idx]
        parent.children[idx].position = idx
        parent.children[new_idx].position = new_idx

        self.store.save()
        self._populate_tree()
        self.store_changed.emit()

    def refresh(self):
        """Refresh the tree from the store."""
        self._populate_tree()

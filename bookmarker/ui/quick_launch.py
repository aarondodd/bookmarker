"""Quick Launch Window - fast bookmark search and folder navigation."""

from typing import List, Optional

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QStackedWidget, QFrame, QApplication, QLabel,
)

from ..models.bookmark import Bookmark, BookmarkType, BookmarkStore
from ..utils.launcher import launch_bookmark


class QuickLaunchWindow(QWidget):
    """Frameless window for quick bookmark search and launch."""

    # Emitted when a bookmark is launched (window closes after)
    bookmark_launched = pyqtSignal(Bookmark)

    # Emitted when window is closed
    closed = pyqtSignal()

    def __init__(self, store: BookmarkStore, parent=None):
        super().__init__(parent)
        self.store = store
        self._navigation_stack: List[Optional[str]] = []  # Stack of folder IDs (None = root)
        self._current_folder_id: Optional[str] = None
        self._filtered_bookmarks: List[Bookmark] = []
        self._is_searching = False

        self._setup_window()
        self._setup_ui()
        self._populate_folder_view(None)

    def _setup_window(self):
        """Configure window properties."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(500, 400)

        # Center on screen
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
            self.move(x, y)

    def _setup_ui(self):
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Search box
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Find bookmark")
        self._search_edit.textChanged.connect(self._on_search_changed)
        self._search_edit.returnPressed.connect(self._launch_selected)
        layout.addWidget(self._search_edit)

        # Navigation bar (hidden during search)
        self._nav_bar = QWidget()
        nav_layout = QHBoxLayout(self._nav_bar)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(4)

        self._back_btn = QPushButton("<")
        self._back_btn.setFixedWidth(32)
        self._back_btn.clicked.connect(self._go_back)
        self._back_btn.setEnabled(False)
        nav_layout.addWidget(self._back_btn)

        self._home_btn = QPushButton("Home")
        self._home_btn.setFixedWidth(60)
        self._home_btn.clicked.connect(self._go_home)
        self._home_btn.setEnabled(False)
        nav_layout.addWidget(self._home_btn)

        self._path_label = QLabel("")
        self._path_label.setStyleSheet("color: #666; font-size: 11px;")
        nav_layout.addWidget(self._path_label, 1)

        nav_layout.addStretch()
        layout.addWidget(self._nav_bar)

        # Stacked widget for folder/search views
        self._stack = QStackedWidget()

        # Folder view (index 0)
        self._folder_list = QListWidget()
        self._folder_list.itemClicked.connect(self._on_folder_item_clicked)
        self._folder_list.itemDoubleClicked.connect(self._on_folder_item_double_clicked)
        self._stack.addWidget(self._folder_list)

        # Search results view (index 1)
        self._search_list = QListWidget()
        self._search_list.itemClicked.connect(self._on_search_item_clicked)
        self._search_list.itemDoubleClicked.connect(self._on_search_item_double_clicked)
        self._stack.addWidget(self._search_list)

        layout.addWidget(self._stack)

        # Start with folder view
        self._stack.setCurrentIndex(0)

    def _populate_folder_view(self, folder_id: Optional[str]):
        """Populate the folder list with contents of the specified folder."""
        self._folder_list.clear()
        self._current_folder_id = folder_id

        # Update navigation state
        can_go_back = len(self._navigation_stack) > 0
        self._back_btn.setEnabled(can_go_back)
        self._home_btn.setEnabled(folder_id is not None)

        # Update path label
        if folder_id is None:
            self._path_label.setText("")
        else:
            folder = self.store.find_by_id(folder_id)
            if folder:
                self._path_label.setText(folder.get_folder_path(self.store))

        # Get items to display
        if folder_id is None:
            # Root level - show root folders
            items = []
            for root_name, root_bm in self.store.roots.items():
                for child in sorted(root_bm.children, key=lambda x: x.position):
                    items.append(child)
        else:
            # Show children of the specified folder
            folder = self.store.find_by_id(folder_id)
            if folder:
                items = sorted(folder.children, key=lambda x: x.position)
            else:
                items = []

        # Add items to list
        for item in items:
            list_item = QListWidgetItem()
            if item.type == BookmarkType.FOLDER:
                list_item.setText(f"\U0001F4C1 {item.title}")  # Folder emoji
            else:
                list_item.setText(f"\U0001F517 {item.title}")  # Link emoji
            list_item.setData(Qt.ItemDataRole.UserRole, item.id)
            self._folder_list.addItem(list_item)

    def _on_folder_item_clicked(self, item: QListWidgetItem):
        """Handle single click on folder view item."""
        bm_id = item.data(Qt.ItemDataRole.UserRole)
        bookmark = self.store.find_by_id(bm_id)
        if bookmark and bookmark.type == BookmarkType.FOLDER:
            # Navigate into folder
            self._navigation_stack.append(self._current_folder_id)
            self._populate_folder_view(bm_id)

    def _on_folder_item_double_clicked(self, item: QListWidgetItem):
        """Handle double click on folder view item."""
        bm_id = item.data(Qt.ItemDataRole.UserRole)
        bookmark = self.store.find_by_id(bm_id)
        if bookmark and bookmark.type == BookmarkType.URL:
            self._launch_bookmark(bookmark)

    def _on_search_item_clicked(self, item: QListWidgetItem):
        """Handle click on search result item - select it."""
        # Selection is automatic, nothing extra needed
        pass

    def _on_search_item_double_clicked(self, item: QListWidgetItem):
        """Handle double click on search result - launch it."""
        idx = self._search_list.row(item)
        if 0 <= idx < len(self._filtered_bookmarks):
            self._launch_bookmark(self._filtered_bookmarks[idx])

    def _go_back(self):
        """Navigate back to previous folder."""
        if self._navigation_stack:
            prev_folder_id = self._navigation_stack.pop()
            self._populate_folder_view(prev_folder_id)

    def _go_home(self):
        """Navigate to root."""
        self._navigation_stack.clear()
        self._populate_folder_view(None)

    def _on_search_changed(self, text: str):
        """Handle search text changes."""
        text = text.strip()
        if text:
            self._is_searching = True
            self._nav_bar.hide()
            self._stack.setCurrentIndex(1)
            self._perform_search(text)
        else:
            self._is_searching = False
            self._nav_bar.show()
            self._stack.setCurrentIndex(0)
            # Reset to current folder view
            self._populate_folder_view(self._current_folder_id)

    def _perform_search(self, query: str):
        """Search bookmarks and update results list."""
        self._search_list.clear()
        self._filtered_bookmarks = []

        query_lower = query.lower()

        # Search all bookmarks
        all_bookmarks = self.store.all_bookmarks()
        for bm in all_bookmarks:
            if bm.type == BookmarkType.URL:
                # Match title or URL
                if query_lower in bm.title.lower() or query_lower in bm.url.lower():
                    self._filtered_bookmarks.append(bm)

        # Sort by title
        self._filtered_bookmarks.sort(key=lambda x: x.title.lower())

        # Populate list
        for bm in self._filtered_bookmarks:
            folder_path = bm.get_folder_path(self.store)
            item = QListWidgetItem()
            item.setText(f"\U0001F517 {bm.title}")
            item.setToolTip(f"{folder_path}\n{bm.url}")
            item.setData(Qt.ItemDataRole.UserRole, bm.id)
            self._search_list.addItem(item)

        # Select first item
        if self._search_list.count() > 0:
            self._search_list.setCurrentRow(0)

    def _launch_selected(self):
        """Launch the currently selected bookmark."""
        if self._is_searching:
            # Launch from search results
            current = self._search_list.currentItem()
            if current:
                idx = self._search_list.row(current)
                if 0 <= idx < len(self._filtered_bookmarks):
                    self._launch_bookmark(self._filtered_bookmarks[idx])
        else:
            # Launch from folder view if a URL is selected
            current = self._folder_list.currentItem()
            if current:
                bm_id = current.data(Qt.ItemDataRole.UserRole)
                bookmark = self.store.find_by_id(bm_id)
                if bookmark:
                    if bookmark.type == BookmarkType.URL:
                        self._launch_bookmark(bookmark)
                    elif bookmark.type == BookmarkType.FOLDER:
                        # Navigate into folder
                        self._navigation_stack.append(self._current_folder_id)
                        self._populate_folder_view(bm_id)

    def _launch_bookmark(self, bookmark: Bookmark):
        """Launch a bookmark and close the window."""
        if launch_bookmark(bookmark):
            self.bookmark_launched.emit(bookmark)
        self.close()

    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_Down:
            # Move selection down in current list
            if self._is_searching:
                current = self._search_list.currentRow()
                if current < self._search_list.count() - 1:
                    self._search_list.setCurrentRow(current + 1)
            else:
                current = self._folder_list.currentRow()
                if current < self._folder_list.count() - 1:
                    self._folder_list.setCurrentRow(current + 1)
        elif event.key() == Qt.Key.Key_Up:
            # Move selection up in current list
            if self._is_searching:
                current = self._search_list.currentRow()
                if current > 0:
                    self._search_list.setCurrentRow(current - 1)
            else:
                current = self._folder_list.currentRow()
                if current > 0:
                    self._folder_list.setCurrentRow(current - 1)
        elif event.key() == Qt.Key.Key_Backspace and not self._search_edit.text():
            # Go back when backspace pressed with empty search
            if not self._is_searching and self._navigation_stack:
                self._go_back()
        else:
            super().keyPressEvent(event)

    def showEvent(self, event):
        """Focus search edit when shown."""
        super().showEvent(event)
        self._search_edit.setFocus()
        self._search_edit.selectAll()

    def closeEvent(self, event):
        """Emit closed signal when window closes."""
        self.closed.emit()
        super().closeEvent(event)

    def refresh_store(self, store: BookmarkStore):
        """Update with a new store."""
        self.store = store
        if not self._is_searching:
            self._populate_folder_view(self._current_folder_id)
        else:
            self._perform_search(self._search_edit.text())

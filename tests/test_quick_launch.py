"""Tests for quick launch window."""

import sys
import pytest
from unittest.mock import patch, MagicMock

from bookmarker.models.bookmark import Bookmark, BookmarkType, BookmarkStore

# Skip all tests if no display is available
pytestmark = pytest.mark.skipif(
    not bool(
        __import__("os").environ.get("DISPLAY") or
        __import__("os").environ.get("WAYLAND_DISPLAY")
    ),
    reason="No display available",
)


@pytest.fixture
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def store_with_data(isolate_config):
    store = BookmarkStore()
    store.add(Bookmark(title="Example", url="https://example.com"))
    store.add(Bookmark(title="Test Site", url="https://test.com"))
    folder = Bookmark(title="Dev", type=BookmarkType.FOLDER)
    store.add(folder)
    store.add(Bookmark(title="GitHub", url="https://github.com"), parent_id=folder.id)
    store.add(Bookmark(title="GitLab", url="https://gitlab.com"), parent_id=folder.id)
    store.save()
    return store


class TestQuickLaunchWindow:
    def test_window_creates(self, qapp, store_with_data):
        from bookmarker.ui.quick_launch import QuickLaunchWindow
        window = QuickLaunchWindow(store_with_data)
        assert window is not None
        assert window.width() == 500
        assert window.height() == 400

    def test_search_box_has_placeholder(self, qapp, store_with_data):
        from bookmarker.ui.quick_launch import QuickLaunchWindow
        window = QuickLaunchWindow(store_with_data)
        assert window._search_edit.placeholderText() == "Find bookmark"

    def test_folder_view_shows_items(self, qapp, store_with_data):
        from bookmarker.ui.quick_launch import QuickLaunchWindow
        window = QuickLaunchWindow(store_with_data)
        # Should show Example, Test Site, and Dev folder
        assert window._folder_list.count() == 3

    def test_search_filters_bookmarks(self, qapp, store_with_data):
        from bookmarker.ui.quick_launch import QuickLaunchWindow
        window = QuickLaunchWindow(store_with_data)
        window._search_edit.setText("git")
        # Should find GitHub and GitLab
        assert window._search_list.count() == 2

    def test_search_hides_nav_bar(self, qapp, store_with_data):
        from bookmarker.ui.quick_launch import QuickLaunchWindow
        window = QuickLaunchWindow(store_with_data)
        window.show()
        qapp.processEvents()
        assert window._nav_bar.isVisible()
        window._search_edit.setText("test")
        qapp.processEvents()
        assert window._nav_bar.isHidden()

    def test_clear_search_shows_folder_view(self, qapp, store_with_data):
        from bookmarker.ui.quick_launch import QuickLaunchWindow
        window = QuickLaunchWindow(store_with_data)
        window.show()
        qapp.processEvents()
        window._search_edit.setText("test")
        qapp.processEvents()
        assert window._stack.currentIndex() == 1  # Search view
        window._search_edit.setText("")
        qapp.processEvents()
        assert window._stack.currentIndex() == 0  # Folder view
        assert window._nav_bar.isVisible()

    def test_navigation_into_folder(self, qapp, store_with_data):
        from bookmarker.ui.quick_launch import QuickLaunchWindow
        from PyQt6.QtWidgets import QListWidgetItem
        window = QuickLaunchWindow(store_with_data)

        # Find Dev folder item
        for i in range(window._folder_list.count()):
            item = window._folder_list.item(i)
            if "Dev" in item.text():
                # Simulate click on folder
                window._on_folder_item_clicked(item)
                break

        # Should now show contents of Dev folder (GitHub, GitLab)
        assert window._folder_list.count() == 2
        assert window._back_btn.isEnabled()
        assert window._home_btn.isEnabled()

    def test_back_navigation(self, qapp, store_with_data):
        from bookmarker.ui.quick_launch import QuickLaunchWindow
        window = QuickLaunchWindow(store_with_data)

        # Navigate into Dev folder
        for i in range(window._folder_list.count()):
            item = window._folder_list.item(i)
            if "Dev" in item.text():
                window._on_folder_item_clicked(item)
                break

        # Go back
        window._go_back()
        assert window._folder_list.count() == 3
        assert not window._back_btn.isEnabled()

    def test_home_navigation(self, qapp, store_with_data):
        from bookmarker.ui.quick_launch import QuickLaunchWindow
        window = QuickLaunchWindow(store_with_data)

        # Navigate into Dev folder
        for i in range(window._folder_list.count()):
            item = window._folder_list.item(i)
            if "Dev" in item.text():
                window._on_folder_item_clicked(item)
                break

        # Go home
        window._go_home()
        assert window._folder_list.count() == 3
        assert not window._home_btn.isEnabled()

    def test_launch_bookmark_closes_window(self, qapp, store_with_data):
        from bookmarker.ui.quick_launch import QuickLaunchWindow
        window = QuickLaunchWindow(store_with_data)
        window.show()

        closed_signal_received = []
        window.closed.connect(lambda: closed_signal_received.append(True))

        with patch("bookmarker.ui.quick_launch.launch_bookmark", return_value=True):
            bm = Bookmark(title="Test", url="https://test.com", type=BookmarkType.URL)
            window._launch_bookmark(bm)

        assert len(closed_signal_received) == 1

    def test_escape_closes_window(self, qapp, store_with_data):
        from bookmarker.ui.quick_launch import QuickLaunchWindow
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtCore import QEvent

        window = QuickLaunchWindow(store_with_data)
        window.show()

        closed_signal_received = []
        window.closed.connect(lambda: closed_signal_received.append(True))

        # Simulate Escape key press
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        window.keyPressEvent(event)

        assert len(closed_signal_received) == 1

    def test_search_selects_first_result(self, qapp, store_with_data):
        from bookmarker.ui.quick_launch import QuickLaunchWindow
        window = QuickLaunchWindow(store_with_data)
        window._search_edit.setText("git")
        assert window._search_list.currentRow() == 0

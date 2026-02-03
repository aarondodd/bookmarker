"""Tests for bookmark editor window."""

import sys
import pytest

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
    folder = Bookmark(title="Dev", type=BookmarkType.FOLDER)
    store.add(folder)
    store.add(Bookmark(title="GitHub", url="https://github.com"), parent_id=folder.id)
    store.save()
    return store


class TestBookmarkEditorWindow:
    def test_window_creates(self, qapp, store_with_data):
        from bookmarker.ui.editor import BookmarkEditorWindow
        editor = BookmarkEditorWindow(store_with_data)
        assert editor.windowTitle() == "Bookmark Editor"

    def test_tree_populated(self, qapp, store_with_data):
        from bookmarker.ui.editor import BookmarkEditorWindow
        editor = BookmarkEditorWindow(store_with_data)
        # Should have 2 root items (bookmark_bar, other)
        assert editor._tree.topLevelItemCount() == 2

    def test_tree_has_children(self, qapp, store_with_data):
        from bookmarker.ui.editor import BookmarkEditorWindow
        editor = BookmarkEditorWindow(store_with_data)
        bar_item = editor._tree.topLevelItem(0)
        # bookmark_bar should have 2 children: Example and Dev folder
        assert bar_item.childCount() == 2

    def test_folder_combo_has_entries(self, qapp, store_with_data):
        from bookmarker.ui.editor import BookmarkEditorWindow
        editor = BookmarkEditorWindow(store_with_data)
        assert editor._folder_combo.count() >= 3  # bookmark_bar, Dev, other

    def test_refresh(self, qapp, store_with_data):
        from bookmarker.ui.editor import BookmarkEditorWindow
        editor = BookmarkEditorWindow(store_with_data)
        store_with_data.add(Bookmark(title="New", url="https://new.com"))
        editor.refresh()
        bar_item = editor._tree.topLevelItem(0)
        assert bar_item.childCount() == 3

"""Tests for sync engine."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from bookmarker.models.bookmark import Bookmark, BookmarkType, BookmarkStore
from bookmarker.operations.sync import (
    SyncAction,
    SyncActionType,
    plan_sync,
    execute_sync,
    _add_to_store_at_path,
)


def _make_chrome_data(bookmarks):
    """Helper to create Chrome bookmark JSON from a list of (title, url) tuples."""
    children = []
    for i, (title, url) in enumerate(bookmarks):
        children.append({
            "date_added": "13345678901234567",
            "date_last_used": "0",
            "guid": f"00000000-0000-0000-0000-{str(i+1).zfill(12)}",
            "id": str(i + 1),
            "name": title,
            "type": "url",
            "url": url,
        })
    return {
        "checksum": "",
        "roots": {
            "bookmark_bar": {
                "children": children,
                "date_added": "13345678901234567",
                "date_modified": "13345678901234567",
                "guid": "00000000-0000-4000-0000-000000000000",
                "id": "0",
                "name": "Bookmarks bar",
                "type": "folder",
            },
            "other": {
                "children": [],
                "date_added": "13345678901234567",
                "date_modified": "0",
                "guid": "00000000-0000-4000-0000-000000000001",
                "id": "100",
                "name": "Other bookmarks",
                "type": "folder",
            },
            "synced": {
                "children": [],
                "date_added": "13345678901234567",
                "date_modified": "0",
                "guid": "00000000-0000-4000-0000-000000000002",
                "id": "101",
                "name": "Mobile bookmarks",
                "type": "folder",
            },
        },
        "version": 1,
    }


class TestPlanSync:
    def test_new_browser_bookmarks_planned_as_add_to_store(self, tmp_path, isolate_config):
        """Browser has bookmarks that store doesn't -> add_to_store."""
        chrome_data = _make_chrome_data([("GitHub", "https://github.com")])
        bookmark_file = tmp_path / "Bookmarks"
        bookmark_file.write_text(json.dumps(chrome_data))

        store = BookmarkStore()  # Empty store

        actions, browser_store, error = plan_sync(store, "chrome", bookmark_file)
        assert error is None
        assert len(actions) == 1
        assert actions[0].action == SyncActionType.ADD_TO_STORE
        assert actions[0].bookmark.title == "GitHub"

    def test_new_store_bookmarks_planned_as_add_to_browser(self, tmp_path, isolate_config):
        """Store has bookmarks that browser doesn't -> add_to_browser."""
        chrome_data = _make_chrome_data([])  # Empty browser
        bookmark_file = tmp_path / "Bookmarks"
        bookmark_file.write_text(json.dumps(chrome_data))

        store = BookmarkStore()
        store.add(Bookmark(title="My Site", url="https://mysite.com"))

        actions, _, error = plan_sync(store, "chrome", bookmark_file)
        assert error is None
        add_to_browser = [a for a in actions if a.action == SyncActionType.ADD_TO_BROWSER]
        assert len(add_to_browser) == 1
        assert add_to_browser[0].bookmark.title == "My Site"

    def test_matching_bookmarks_no_actions(self, tmp_path, isolate_config):
        """Same bookmarks in both -> no actions."""
        chrome_data = _make_chrome_data([("Example", "https://example.com")])
        bookmark_file = tmp_path / "Bookmarks"
        bookmark_file.write_text(json.dumps(chrome_data))

        store = BookmarkStore()
        store.add(Bookmark(title="Example", url="https://example.com"))

        actions, _, error = plan_sync(store, "chrome", bookmark_file)
        assert error is None
        # Only update actions possible (date comparison), no add actions
        add_actions = [a for a in actions
                       if a.action in (SyncActionType.ADD_TO_STORE, SyncActionType.ADD_TO_BROWSER)]
        assert len(add_actions) == 0

    def test_browser_read_failure(self, isolate_config):
        with patch("bookmarker.operations.sync.read_chrome_bookmarks", return_value=None):
            actions, _, error = plan_sync(BookmarkStore(), "chrome")
        assert error is not None
        assert "Could not read" in error


class TestExecuteSync:
    def test_add_to_store(self, isolate_config):
        store = BookmarkStore()
        bm = Bookmark(title="New", url="https://new.com", source_id="1")

        actions = [SyncAction(
            action=SyncActionType.ADD_TO_STORE,
            bookmark=bm,
            root_name="bookmark_bar",
            parent_title="",
            description="Add to store",
        )]

        store_changes, browser_changes, error = execute_sync(store, "chrome", actions)
        assert store_changes == 1
        assert browser_changes == 0
        assert store.roots["bookmark_bar"].children[0].title == "New"

    def test_add_to_browser(self, tmp_path, isolate_config):
        store = BookmarkStore()
        store.add(Bookmark(title="Existing", url="https://existing.com"))
        bm = Bookmark(title="Existing", url="https://existing.com")

        actions = [SyncAction(
            action=SyncActionType.ADD_TO_BROWSER,
            bookmark=bm,
            root_name="bookmark_bar",
            description="Add to browser",
        )]

        bookmark_file = tmp_path / "Bookmarks"
        bookmark_file.write_text("{}")

        with patch("bookmarker.operations.sync.is_browser_running", return_value=False), \
             patch("bookmarker.operations.sync._write_browser", return_value=True):
            store_changes, browser_changes, error = execute_sync(
                store, "chrome", actions, bookmark_file)

        assert browser_changes == 1
        assert error is None

    def test_browser_running_blocks_write(self, isolate_config):
        store = BookmarkStore()
        actions = [SyncAction(
            action=SyncActionType.ADD_TO_BROWSER,
            bookmark=Bookmark(title="X", url="https://x.com"),
            root_name="bookmark_bar",
            description="test",
        )]

        with patch("bookmarker.operations.sync.is_browser_running", return_value=True):
            _, _, error = execute_sync(store, "chrome", actions)
        assert error is not None
        assert "running" in error.lower()


class TestAddToStoreAtPath:
    def test_add_to_root(self, isolate_config):
        store = BookmarkStore()
        bm = Bookmark(title="Test", url="https://test.com")
        _add_to_store_at_path(store, bm, "bookmark_bar", "")
        assert store.roots["bookmark_bar"].children[0].title == "Test"

    def test_add_creates_folders(self, isolate_config):
        store = BookmarkStore()
        bm = Bookmark(title="Deep", url="https://deep.com")
        _add_to_store_at_path(store, bm, "bookmark_bar", "Level1/Level2")

        level1 = store.roots["bookmark_bar"].children[0]
        assert level1.title == "Level1"
        assert level1.type == BookmarkType.FOLDER
        level2 = level1.children[0]
        assert level2.title == "Level2"
        assert level2.type == BookmarkType.FOLDER
        assert level2.children[0].title == "Deep"

    def test_add_uses_existing_folders(self, isolate_config):
        store = BookmarkStore()
        folder = Bookmark(title="Existing", type=BookmarkType.FOLDER)
        store.add(folder)

        bm = Bookmark(title="New", url="https://new.com")
        _add_to_store_at_path(store, bm, "bookmark_bar", "Existing")

        assert len(store.roots["bookmark_bar"].children) == 1  # No duplicate folder
        assert len(folder.children) == 1
        assert folder.children[0].title == "New"

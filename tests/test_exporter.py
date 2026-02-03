"""Tests for export/push orchestrator."""

import json
from pathlib import Path
from unittest.mock import patch

from bookmarker.models.bookmark import Bookmark, BookmarkType, BookmarkStore
from bookmarker.operations.exporter import push_to_browser


class TestPushToBrowser:
    def test_push_chrome(self, tmp_path, isolate_config):
        bookmark_file = tmp_path / "Bookmarks"
        # Create an empty Chrome bookmarks file first
        bookmark_file.write_text('{"roots": {}, "version": 1}')

        store = BookmarkStore()
        store.add(Bookmark(title="Pushed", url="https://pushed.com"))

        with patch("bookmarker.operations.exporter.is_browser_running", return_value=False), \
             patch("bookmarker.operations.chrome.is_browser_running", return_value=False):
            success, error = push_to_browser("chrome", store, bookmark_file)

        assert success is True
        assert error is None

        data = json.loads(bookmark_file.read_text())
        assert data["roots"]["bookmark_bar"]["children"][0]["name"] == "Pushed"

    def test_push_refused_if_running(self, tmp_path, isolate_config):
        store = BookmarkStore()
        with patch("bookmarker.operations.exporter.is_browser_running", return_value=True):
            success, error = push_to_browser("chrome", store, tmp_path / "Bookmarks")

        assert success is False
        assert "running" in error.lower()

    def test_push_unknown_browser(self, isolate_config):
        store = BookmarkStore()
        success, error = push_to_browser("opera", store)
        assert success is False
        assert "Unknown browser" in error

    def test_push_creates_store_backup(self, tmp_path, isolate_config):
        bookmark_file = tmp_path / "Bookmarks"
        bookmark_file.write_text('{}')

        store = BookmarkStore()
        store.save()

        with patch("bookmarker.operations.exporter.is_browser_running", return_value=False), \
             patch("bookmarker.operations.chrome.is_browser_running", return_value=False):
            push_to_browser("chrome", store, bookmark_file)

        from bookmarker.utils.config import get_backups_dir
        backups = list(get_backups_dir().glob("bookmarks_*.json"))
        assert len(backups) >= 1

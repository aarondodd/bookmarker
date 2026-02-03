"""Tests for Edge bookmark reader/writer."""

import json
from pathlib import Path
from unittest.mock import patch

from bookmarker.models.bookmark import Bookmark, BookmarkStore
from bookmarker.operations.edge import read_edge_bookmarks, write_edge_bookmarks
from bookmarker.operations.chrome import calculate_checksum


class TestReadEdgeBookmarks:
    def test_read_from_file(self, tmp_path, sample_chrome_data):
        bookmark_file = tmp_path / "Bookmarks"
        bookmark_file.write_text(json.dumps(sample_chrome_data))

        store = read_edge_bookmarks(bookmark_file)
        assert store is not None
        bar = store.roots["bookmark_bar"]
        assert len(bar.children) == 2
        assert bar.children[0].source_browser == "edge"

    def test_read_nonexistent(self, tmp_path):
        store = read_edge_bookmarks(tmp_path / "nonexistent")
        assert store is None


class TestWriteEdgeBookmarks:
    def test_write_creates_file(self, tmp_path, isolate_config):
        bookmark_file = tmp_path / "Bookmarks"
        store = BookmarkStore()
        store.add(Bookmark(title="Edge Test", url="https://test.com"))

        with patch("bookmarker.operations.chrome.is_browser_running", return_value=False):
            result = write_edge_bookmarks(store, bookmark_file)

        assert result is True
        data = json.loads(bookmark_file.read_text())
        assert data["roots"]["bookmark_bar"]["children"][0]["name"] == "Edge Test"
        assert data["checksum"] == calculate_checksum(data["roots"])

    def test_write_refused_if_running(self, tmp_path):
        store = BookmarkStore()
        with patch("bookmarker.operations.chrome.is_browser_running", return_value=True):
            result = write_edge_bookmarks(store, tmp_path / "Bookmarks")
        assert result is False

    def test_write_creates_backup(self, tmp_path, isolate_config):
        bookmark_file = tmp_path / "Bookmarks"
        bookmark_file.write_text('{"existing": true}')

        store = BookmarkStore()
        with patch("bookmarker.operations.chrome.is_browser_running", return_value=False):
            write_edge_bookmarks(store, bookmark_file)

        from bookmarker.utils.config import get_backups_dir
        backups = list(get_backups_dir().glob("edge_bookmarks_*.json"))
        assert len(backups) == 1

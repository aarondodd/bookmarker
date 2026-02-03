"""Tests for import orchestrator."""

import json
from pathlib import Path
from unittest.mock import patch

from bookmarker.models.bookmark import Bookmark, BookmarkType, BookmarkStore
from bookmarker.operations.importer import import_from_browser, _dedup_key


class TestDedup:
    def test_same_url_same_path(self):
        b1 = Bookmark(title="A", url="https://example.com")
        b2 = Bookmark(title="B", url="https://example.com")
        assert _dedup_key(b1, "bookmark_bar") == _dedup_key(b2, "bookmark_bar")

    def test_same_url_different_path(self):
        b1 = Bookmark(title="A", url="https://example.com")
        b2 = Bookmark(title="A", url="https://example.com")
        assert _dedup_key(b1, "bookmark_bar") != _dedup_key(b2, "other")


class TestImportFromBrowser:
    def test_import_chrome(self, tmp_path, sample_chrome_data, isolate_config):
        bookmark_file = tmp_path / "Bookmarks"
        bookmark_file.write_text(json.dumps(sample_chrome_data))

        store = BookmarkStore()
        added, skipped, error = import_from_browser("chrome", store, bookmark_file)

        assert error is None
        assert added > 0
        assert store.roots["bookmark_bar"].children[0].title == "Example"

    def test_import_dedup(self, tmp_path, sample_chrome_data, isolate_config):
        bookmark_file = tmp_path / "Bookmarks"
        bookmark_file.write_text(json.dumps(sample_chrome_data))

        store = BookmarkStore()
        # First import
        added1, _, _ = import_from_browser("chrome", store, bookmark_file)
        # Second import - should skip duplicates
        added2, skipped2, _ = import_from_browser("chrome", store, bookmark_file)

        assert added1 > 0
        assert added2 == 0
        assert skipped2 > 0

    def test_import_unknown_browser(self, isolate_config):
        store = BookmarkStore()
        added, skipped, error = import_from_browser("opera", store)
        assert error is not None
        assert "Unknown browser" in error

    def test_import_missing_browser(self, isolate_config):
        store = BookmarkStore()
        with patch("bookmarker.operations.importer.read_chrome_bookmarks", return_value=None):
            added, skipped, error = import_from_browser("chrome", store)
        assert error is not None
        assert "Could not read" in error

    def test_import_preserves_folders(self, tmp_path, sample_chrome_data, isolate_config):
        bookmark_file = tmp_path / "Bookmarks"
        bookmark_file.write_text(json.dumps(sample_chrome_data))

        store = BookmarkStore()
        import_from_browser("chrome", store, bookmark_file)

        bar = store.roots["bookmark_bar"]
        folders = [c for c in bar.children if c.type == BookmarkType.FOLDER]
        assert len(folders) == 1
        assert folders[0].title == "Dev"
        assert len(folders[0].children) == 1

    def test_import_merges_folders(self, tmp_path, sample_chrome_data, isolate_config):
        """If store already has a folder with same name, import into it."""
        bookmark_file = tmp_path / "Bookmarks"
        bookmark_file.write_text(json.dumps(sample_chrome_data))

        store = BookmarkStore()
        existing_folder = Bookmark(title="Dev", type=BookmarkType.FOLDER)
        store.add(existing_folder)
        store.add(
            Bookmark(title="Other Site", url="https://other.com"),
            parent_id=existing_folder.id,
        )

        import_from_browser("chrome", store, bookmark_file)

        bar = store.roots["bookmark_bar"]
        dev_folders = [c for c in bar.children if c.title == "Dev"]
        assert len(dev_folders) == 1  # Should merge, not create duplicate folder
        assert len(dev_folders[0].children) == 2  # Original + imported

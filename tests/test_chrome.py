"""Tests for Chrome bookmark reader/writer."""

import json
from pathlib import Path
from unittest.mock import patch

from bookmarker.models.bookmark import Bookmark, BookmarkType, BookmarkStore
from bookmarker.operations.chrome import (
    chrome_time_to_iso,
    iso_to_chrome_time,
    calculate_checksum,
    read_chrome_bookmarks,
    write_chrome_bookmarks,
)


class TestChromeTimeConversion:
    def test_chrome_time_to_iso(self):
        # Known value: 13345678901234567 is a valid Chrome timestamp
        result = chrome_time_to_iso("13345678901234567")
        assert "20" in result  # Should be a year in the 2000s

    def test_chrome_time_zero(self):
        result = chrome_time_to_iso("0")
        assert result  # Should return current time

    def test_chrome_time_invalid(self):
        result = chrome_time_to_iso("not-a-number")
        assert result  # Should return current time

    def test_iso_to_chrome_time(self):
        iso = "2024-01-15T12:00:00+00:00"
        chrome_time = iso_to_chrome_time(iso)
        assert int(chrome_time) > 0

    def test_roundtrip(self):
        original = "13345678901234567"
        iso = chrome_time_to_iso(original)
        back = iso_to_chrome_time(iso)
        # Should be close (some precision loss is acceptable)
        assert abs(int(original) - int(back)) < 1000000  # Within 1 second


class TestChecksum:
    def test_checksum_produces_hex(self, sample_chrome_data):
        checksum = calculate_checksum(sample_chrome_data["roots"])
        assert len(checksum) == 32  # MD5 hex digest
        assert all(c in "0123456789abcdef" for c in checksum)

    def test_checksum_deterministic(self, sample_chrome_data):
        c1 = calculate_checksum(sample_chrome_data["roots"])
        c2 = calculate_checksum(sample_chrome_data["roots"])
        assert c1 == c2

    def test_checksum_changes_on_modification(self, sample_chrome_data):
        c1 = calculate_checksum(sample_chrome_data["roots"])
        sample_chrome_data["roots"]["bookmark_bar"]["children"][0]["name"] = "Changed"
        c2 = calculate_checksum(sample_chrome_data["roots"])
        assert c1 != c2

    def test_empty_roots(self):
        roots = {
            "bookmark_bar": {
                "children": [], "id": "0", "name": "Bookmarks bar", "type": "folder",
            },
            "other": {
                "children": [], "id": "1", "name": "Other bookmarks", "type": "folder",
            },
            "synced": {
                "children": [], "id": "2", "name": "Mobile bookmarks", "type": "folder",
            },
        }
        checksum = calculate_checksum(roots)
        assert len(checksum) == 32


class TestReadChromeBookmarks:
    def test_read_from_file(self, tmp_path, sample_chrome_data):
        bookmark_file = tmp_path / "Bookmarks"
        bookmark_file.write_text(json.dumps(sample_chrome_data))

        store = read_chrome_bookmarks(bookmark_file)
        assert store is not None
        bar = store.roots["bookmark_bar"]
        assert len(bar.children) == 2
        assert bar.children[0].title == "Example"
        assert bar.children[0].url == "https://example.com"
        assert bar.children[0].source_browser == "chrome"
        assert bar.children[0].source_id == "1"

    def test_read_nested_folder(self, tmp_path, sample_chrome_data):
        bookmark_file = tmp_path / "Bookmarks"
        bookmark_file.write_text(json.dumps(sample_chrome_data))

        store = read_chrome_bookmarks(bookmark_file)
        dev_folder = store.roots["bookmark_bar"].children[1]
        assert dev_folder.title == "Dev"
        assert dev_folder.type == BookmarkType.FOLDER
        assert len(dev_folder.children) == 1
        assert dev_folder.children[0].title == "GitHub"

    def test_read_invalid_json(self, tmp_path):
        bookmark_file = tmp_path / "Bookmarks"
        bookmark_file.write_text("not json")
        store = read_chrome_bookmarks(bookmark_file)
        assert store is None

    def test_read_nonexistent_file(self, tmp_path):
        store = read_chrome_bookmarks(tmp_path / "nonexistent")
        assert store is None

    def test_parent_ids_set(self, tmp_path, sample_chrome_data):
        bookmark_file = tmp_path / "Bookmarks"
        bookmark_file.write_text(json.dumps(sample_chrome_data))

        store = read_chrome_bookmarks(bookmark_file)
        bar = store.roots["bookmark_bar"]
        for child in bar.children:
            assert child.parent_id == bar.id


class TestWriteChromeBookmarks:
    def test_write_creates_file(self, tmp_path, isolate_config):
        bookmark_file = tmp_path / "Bookmarks"
        store = BookmarkStore()
        store.add(Bookmark(title="Test", url="https://test.com"))

        with patch("bookmarker.operations.chrome.is_browser_running", return_value=False):
            result = write_chrome_bookmarks(store, bookmark_file)

        assert result is True
        assert bookmark_file.exists()

        data = json.loads(bookmark_file.read_text())
        assert "checksum" in data
        assert len(data["checksum"]) == 32
        assert data["roots"]["bookmark_bar"]["children"][0]["name"] == "Test"

    def test_write_refused_if_running(self, tmp_path):
        store = BookmarkStore()
        with patch("bookmarker.operations.chrome.is_browser_running", return_value=True):
            result = write_chrome_bookmarks(store, tmp_path / "Bookmarks")
        assert result is False

    def test_write_creates_backup(self, tmp_path, isolate_config):
        bookmark_file = tmp_path / "Bookmarks"
        bookmark_file.write_text('{"existing": true}')

        store = BookmarkStore()
        with patch("bookmarker.operations.chrome.is_browser_running", return_value=False):
            write_chrome_bookmarks(store, bookmark_file)

        from bookmarker.utils.config import get_backups_dir
        backups = list(get_backups_dir().glob("chrome_bookmarks_*.json"))
        assert len(backups) == 1

    def test_write_checksum_valid(self, tmp_path, isolate_config):
        store = BookmarkStore()
        store.add(Bookmark(title="Site A", url="https://a.com"))
        store.add(Bookmark(title="Site B", url="https://b.com"))

        bookmark_file = tmp_path / "Bookmarks"
        with patch("bookmarker.operations.chrome.is_browser_running", return_value=False):
            write_chrome_bookmarks(store, bookmark_file)

        data = json.loads(bookmark_file.read_text())
        expected = calculate_checksum(data["roots"])
        assert data["checksum"] == expected

    def test_roundtrip(self, tmp_path, isolate_config):
        """Write bookmarks, then read them back."""
        store = BookmarkStore()
        folder = Bookmark(title="Dev", type=BookmarkType.FOLDER)
        store.add(folder)
        store.add(Bookmark(title="GitHub", url="https://github.com"), parent_id=folder.id)
        store.add(Bookmark(title="Example", url="https://example.com"))

        bookmark_file = tmp_path / "Bookmarks"
        with patch("bookmarker.operations.chrome.is_browser_running", return_value=False):
            write_chrome_bookmarks(store, bookmark_file)

        loaded = read_chrome_bookmarks(bookmark_file)
        assert loaded is not None
        bar = loaded.roots["bookmark_bar"]
        assert len(bar.children) == 2
        titles = {c.title for c in bar.children}
        assert "Dev" in titles
        assert "Example" in titles

        dev = [c for c in bar.children if c.title == "Dev"][0]
        assert len(dev.children) == 1
        assert dev.children[0].title == "GitHub"

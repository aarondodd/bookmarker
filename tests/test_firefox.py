"""Tests for Firefox bookmark reader/writer."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

from bookmarker.models.bookmark import Bookmark, BookmarkType, BookmarkStore
from bookmarker.operations.firefox import (
    _firefox_time_to_iso,
    _iso_to_firefox_time,
    read_firefox_bookmarks,
    write_firefox_bookmarks,
    _reverse_host,
)


def _create_test_places_db(db_path: Path):
    """Create a minimal Firefox places.sqlite for testing."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE moz_places (
            id INTEGER PRIMARY KEY,
            url TEXT,
            title TEXT,
            rev_host TEXT,
            visit_count INTEGER DEFAULT 0,
            hidden INTEGER DEFAULT 0,
            typed INTEGER DEFAULT 0,
            frecency INTEGER DEFAULT -1,
            last_visit_date INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE moz_bookmarks (
            id INTEGER PRIMARY KEY,
            type INTEGER,
            fk INTEGER,
            parent INTEGER,
            position INTEGER,
            title TEXT,
            dateAdded INTEGER,
            lastModified INTEGER
        )
    """)

    # Insert root folders
    now = int(1700000000 * 1000000)
    cursor.execute(
        "INSERT INTO moz_bookmarks VALUES (1, 2, NULL, 0, 0, '', ?, ?)", (now, now))
    cursor.execute(
        "INSERT INTO moz_bookmarks VALUES (2, 2, NULL, 1, 0, 'Bookmarks Menu', ?, ?)", (now, now))
    cursor.execute(
        "INSERT INTO moz_bookmarks VALUES (3, 2, NULL, 1, 1, 'Bookmarks Toolbar', ?, ?)", (now, now))
    cursor.execute(
        "INSERT INTO moz_bookmarks VALUES (5, 2, NULL, 1, 3, 'Other Bookmarks', ?, ?)", (now, now))
    cursor.execute(
        "INSERT INTO moz_bookmarks VALUES (6, 2, NULL, 1, 4, 'Mobile Bookmarks', ?, ?)", (now, now))

    # Insert a test place
    cursor.execute(
        "INSERT INTO moz_places VALUES (1, 'https://example.com', 'Example', '.com.example.', 5, 0, 0, 100, NULL)")
    cursor.execute(
        "INSERT INTO moz_places VALUES (2, 'https://github.com', 'GitHub', '.com.github.', 3, 0, 0, 80, NULL)")

    # Insert bookmarks: one in toolbar, one in a subfolder of toolbar
    cursor.execute(
        "INSERT INTO moz_bookmarks VALUES (7, 1, 1, 3, 0, 'Example', ?, ?)", (now, now))
    # Subfolder in toolbar
    cursor.execute(
        "INSERT INTO moz_bookmarks VALUES (8, 2, NULL, 3, 1, 'Dev', ?, ?)", (now, now))
    cursor.execute(
        "INSERT INTO moz_bookmarks VALUES (9, 1, 2, 8, 0, 'GitHub', ?, ?)", (now, now))

    conn.commit()
    conn.close()


class TestFirefoxTimeConversion:
    def test_to_iso(self):
        result = _firefox_time_to_iso(1700000000000000)
        assert "2023" in result

    def test_zero(self):
        result = _firefox_time_to_iso(0)
        assert result  # Returns current time

    def test_from_iso(self):
        result = _iso_to_firefox_time("2024-01-15T12:00:00+00:00")
        assert result > 0

    def test_roundtrip(self):
        original = 1700000000000000
        iso = _firefox_time_to_iso(original)
        back = _iso_to_firefox_time(iso)
        assert abs(original - back) < 1000000  # Within 1 second


class TestReverseHost:
    def test_simple(self):
        assert _reverse_host("https://example.com/page") == ".com.example."

    def test_subdomain(self):
        assert _reverse_host("https://www.example.com") == ".com.example.www."

    def test_empty(self):
        assert _reverse_host("") == ""


class TestReadFirefoxBookmarks:
    def test_read_from_db(self, tmp_path):
        db_path = tmp_path / "places.sqlite"
        _create_test_places_db(db_path)

        store = read_firefox_bookmarks(db_path)
        assert store is not None

        bar = store.roots["bookmark_bar"]
        assert len(bar.children) == 2
        assert bar.children[0].title == "Example"
        assert bar.children[0].url == "https://example.com"
        assert bar.children[0].source_browser == "firefox"

    def test_read_nested_folder(self, tmp_path):
        db_path = tmp_path / "places.sqlite"
        _create_test_places_db(db_path)

        store = read_firefox_bookmarks(db_path)
        dev = store.roots["bookmark_bar"].children[1]
        assert dev.title == "Dev"
        assert dev.type == BookmarkType.FOLDER
        assert len(dev.children) == 1
        assert dev.children[0].title == "GitHub"

    def test_read_nonexistent(self, tmp_path):
        store = read_firefox_bookmarks(tmp_path / "nonexistent.sqlite")
        assert store is None


class TestWriteFirefoxBookmarks:
    def test_write_to_db(self, tmp_path, isolate_config):
        db_path = tmp_path / "places.sqlite"
        _create_test_places_db(db_path)

        store = BookmarkStore()
        store.add(Bookmark(title="New Site", url="https://newsite.com"))

        with patch("bookmarker.operations.firefox.is_browser_running", return_value=False):
            result = write_firefox_bookmarks(store, db_path)

        assert result is True

        # Verify by reading back
        loaded = read_firefox_bookmarks(db_path)
        assert loaded is not None
        bar = loaded.roots["bookmark_bar"]
        assert len(bar.children) == 1
        assert bar.children[0].title == "New Site"

    def test_write_refused_if_running(self, tmp_path):
        db_path = tmp_path / "places.sqlite"
        _create_test_places_db(db_path)
        store = BookmarkStore()

        with patch("bookmarker.operations.firefox.is_browser_running", return_value=True):
            result = write_firefox_bookmarks(store, db_path)
        assert result is False

    def test_write_creates_backup(self, tmp_path, isolate_config):
        db_path = tmp_path / "places.sqlite"
        _create_test_places_db(db_path)

        store = BookmarkStore()
        with patch("bookmarker.operations.firefox.is_browser_running", return_value=False):
            write_firefox_bookmarks(store, db_path)

        from bookmarker.utils.config import get_backups_dir
        backups = list(get_backups_dir().glob("firefox_places_*.sqlite"))
        assert len(backups) == 1

    def test_write_with_folders(self, tmp_path, isolate_config):
        db_path = tmp_path / "places.sqlite"
        _create_test_places_db(db_path)

        store = BookmarkStore()
        folder = Bookmark(title="Work", type=BookmarkType.FOLDER)
        store.add(folder)
        store.add(Bookmark(title="Jira", url="https://jira.example.com"), parent_id=folder.id)

        with patch("bookmarker.operations.firefox.is_browser_running", return_value=False):
            result = write_firefox_bookmarks(store, db_path)

        assert result is True

        loaded = read_firefox_bookmarks(db_path)
        bar = loaded.roots["bookmark_bar"]
        work = [c for c in bar.children if c.title == "Work"]
        assert len(work) == 1
        assert len(work[0].children) == 1
        assert work[0].children[0].title == "Jira"

    def test_write_nonexistent_db(self, tmp_path, isolate_config):
        store = BookmarkStore()
        with patch("bookmarker.operations.firefox.is_browser_running", return_value=False):
            result = write_firefox_bookmarks(store, tmp_path / "nonexistent.sqlite")
        assert result is False

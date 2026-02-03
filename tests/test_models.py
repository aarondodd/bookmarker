"""Tests for bookmark data model."""

import json
from datetime import datetime
from pathlib import Path

from bookmarker.models.bookmark import (
    Bookmark,
    BookmarkType,
    BookmarkStore,
    normalize_url,
)


class TestBookmarkType:
    def test_url_value(self):
        assert BookmarkType.URL.value == "url"

    def test_folder_value(self):
        assert BookmarkType.FOLDER.value == "folder"


class TestBookmark:
    def test_default_id_generated(self):
        b = Bookmark(title="Test")
        assert b.id  # UUID generated
        assert len(b.id) == 36  # UUID format

    def test_to_dict_roundtrip(self):
        b = Bookmark(
            title="Example",
            url="https://example.com",
            type=BookmarkType.URL,
        )
        d = b.to_dict()
        restored = Bookmark.from_dict(d)
        assert restored.title == "Example"
        assert restored.url == "https://example.com"
        assert restored.type == BookmarkType.URL
        assert restored.id == b.id

    def test_folder_with_children(self):
        child = Bookmark(title="Child", url="https://child.com")
        folder = Bookmark(
            title="Folder",
            type=BookmarkType.FOLDER,
            children=[child],
        )
        d = folder.to_dict()
        assert len(d["children"]) == 1
        assert d["children"][0]["title"] == "Child"

        restored = Bookmark.from_dict(d)
        assert len(restored.children) == 1
        assert restored.children[0].title == "Child"

    def test_default_dates(self):
        b = Bookmark(title="Test")
        assert b.date_added
        assert b.date_modified
        # Should parse as ISO datetime
        datetime.fromisoformat(b.date_added)
        datetime.fromisoformat(b.date_modified)


class TestNormalizeUrl:
    def test_strips_trailing_slash(self):
        assert normalize_url("https://example.com/") == "https://example.com"

    def test_lowercases_scheme_and_host(self):
        assert normalize_url("HTTPS://EXAMPLE.COM/path") == "https://example.com/path"

    def test_preserves_path(self):
        assert normalize_url("https://example.com/foo/bar") == "https://example.com/foo/bar"

    def test_empty_url(self):
        assert normalize_url("") == ""

    def test_strips_fragment(self):
        assert normalize_url("https://example.com/page#section") == "https://example.com/page"


class TestBookmarkStore:
    def test_default_roots(self):
        store = BookmarkStore()
        assert "bookmark_bar" in store.roots
        assert "other" in store.roots
        assert store.roots["bookmark_bar"].type == BookmarkType.FOLDER
        assert store.roots["other"].type == BookmarkType.FOLDER

    def test_to_dict_from_dict(self):
        store = BookmarkStore()
        d = store.to_dict()
        restored = BookmarkStore.from_dict(d)
        assert restored.version == 1
        assert "bookmark_bar" in restored.roots
        assert "other" in restored.roots

    def test_save_and_load(self, isolate_config):
        store = BookmarkStore()
        b = Bookmark(title="Test", url="https://test.com")
        store.add(b)
        store.save()

        loaded = BookmarkStore.load()
        bookmarks = loaded.all_bookmarks()
        assert len(bookmarks) == 1
        assert bookmarks[0].title == "Test"

    def test_add_to_root(self):
        store = BookmarkStore()
        b = Bookmark(title="New", url="https://new.com")
        store.add(b)
        assert len(store.roots["bookmark_bar"].children) == 1
        assert store.roots["bookmark_bar"].children[0].title == "New"

    def test_add_to_other(self):
        store = BookmarkStore()
        b = Bookmark(title="Other", url="https://other.com")
        store.add(b, root="other")
        assert len(store.roots["other"].children) == 1

    def test_add_to_folder(self):
        store = BookmarkStore()
        folder = Bookmark(title="Folder", type=BookmarkType.FOLDER)
        store.add(folder)
        child = Bookmark(title="Child", url="https://child.com")
        store.add(child, parent_id=folder.id)
        assert len(folder.children) == 1
        assert folder.children[0].title == "Child"

    def test_remove(self):
        store = BookmarkStore()
        b = Bookmark(title="Remove Me", url="https://remove.com")
        store.add(b)
        assert len(store.roots["bookmark_bar"].children) == 1
        removed = store.remove(b.id)
        assert removed is not None
        assert removed.title == "Remove Me"
        assert len(store.roots["bookmark_bar"].children) == 0

    def test_remove_nonexistent(self):
        store = BookmarkStore()
        result = store.remove("nonexistent-id")
        assert result is None

    def test_remove_reindexes(self):
        store = BookmarkStore()
        b1 = Bookmark(title="First", url="https://first.com")
        b2 = Bookmark(title="Second", url="https://second.com")
        b3 = Bookmark(title="Third", url="https://third.com")
        store.add(b1)
        store.add(b2)
        store.add(b3)
        store.remove(b2.id)
        children = store.roots["bookmark_bar"].children
        assert len(children) == 2
        assert children[0].position == 0
        assert children[1].position == 1

    def test_move(self):
        store = BookmarkStore()
        folder = Bookmark(title="Dest", type=BookmarkType.FOLDER)
        store.add(folder)
        b = Bookmark(title="Mover", url="https://mover.com")
        store.add(b)
        result = store.move(b.id, folder.id)
        assert result is True
        assert len(folder.children) == 1
        assert folder.children[0].title == "Mover"

    def test_move_with_position(self):
        store = BookmarkStore()
        folder = Bookmark(title="Dest", type=BookmarkType.FOLDER)
        store.add(folder)
        c1 = Bookmark(title="C1", url="https://c1.com")
        c2 = Bookmark(title="C2", url="https://c2.com")
        store.add(c1, parent_id=folder.id)
        store.add(c2, parent_id=folder.id)
        b = Bookmark(title="Insert", url="https://insert.com")
        store.add(b)
        store.move(b.id, folder.id, position=1)
        assert folder.children[1].title == "Insert"
        assert folder.children[0].position == 0
        assert folder.children[1].position == 1
        assert folder.children[2].position == 2

    def test_move_nonexistent(self):
        store = BookmarkStore()
        assert store.move("bad-id", "also-bad") is False

    def test_find_by_id(self):
        store = BookmarkStore()
        b = Bookmark(title="Findable", url="https://find.com")
        store.add(b)
        found = store.find_by_id(b.id)
        assert found is not None
        assert found.title == "Findable"

    def test_find_by_id_root(self):
        store = BookmarkStore()
        root = store.roots["bookmark_bar"]
        found = store.find_by_id(root.id)
        assert found is not None
        assert found.title == "Bookmarks Bar"

    def test_find_by_id_nested(self):
        store = BookmarkStore()
        folder = Bookmark(title="F", type=BookmarkType.FOLDER)
        store.add(folder)
        nested = Bookmark(title="Nested", url="https://nested.com")
        store.add(nested, parent_id=folder.id)
        found = store.find_by_id(nested.id)
        assert found is not None
        assert found.title == "Nested"

    def test_find_by_id_not_found(self):
        store = BookmarkStore()
        assert store.find_by_id("nonexistent") is None

    def test_find_by_url(self):
        store = BookmarkStore()
        b = Bookmark(title="Test", url="https://example.com/page")
        store.add(b)
        results = store.find_by_url("https://example.com/page")
        assert len(results) == 1
        assert results[0].title == "Test"

    def test_find_by_url_normalized(self):
        store = BookmarkStore()
        b = Bookmark(title="Test", url="https://Example.COM/page/")
        store.add(b)
        results = store.find_by_url("https://example.com/page")
        assert len(results) == 1

    def test_find_by_url_no_match(self):
        store = BookmarkStore()
        results = store.find_by_url("https://nonexistent.com")
        assert len(results) == 0

    def test_find_by_source(self):
        store = BookmarkStore()
        b = Bookmark(
            title="Chrome BM",
            url="https://test.com",
            source_browser="chrome",
            source_id="42",
        )
        store.add(b)
        found = store.find_by_source("chrome", "42")
        assert found is not None
        assert found.title == "Chrome BM"

    def test_find_by_source_not_found(self):
        store = BookmarkStore()
        assert store.find_by_source("firefox", "99") is None

    def test_all_bookmarks(self):
        store = BookmarkStore()
        b1 = Bookmark(title="B1", url="https://b1.com")
        b2 = Bookmark(title="B2", url="https://b2.com")
        folder = Bookmark(title="F", type=BookmarkType.FOLDER)
        b3 = Bookmark(title="B3", url="https://b3.com")
        store.add(b1)
        store.add(b2)
        store.add(folder)
        store.add(b3, parent_id=folder.id)
        all_bm = store.all_bookmarks()
        assert len(all_bm) == 4  # b1, b2, folder, b3

    def test_backup(self, isolate_config):
        store = BookmarkStore()
        store.save()
        backup_path = store.backup()
        assert backup_path.exists()
        assert "bookmarks_" in backup_path.name

    def test_load_nonexistent(self, isolate_config):
        store = BookmarkStore.load()
        assert "bookmark_bar" in store.roots
        assert "other" in store.roots

    def test_from_sample_data(self, sample_bookmarks_data):
        store = BookmarkStore.from_dict(sample_bookmarks_data)
        assert len(store.roots["bookmark_bar"].children) == 2
        assert store.roots["bookmark_bar"].children[0].title == "Example"
        dev_folder = store.roots["bookmark_bar"].children[1]
        assert dev_folder.title == "Dev"
        assert len(dev_folder.children) == 1
        assert dev_folder.children[0].title == "GitHub"

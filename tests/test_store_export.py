"""Tests for store export/import functionality."""

import json
from pathlib import Path

import pytest

from bookmarker.models.bookmark import Bookmark, BookmarkType, BookmarkStore
from bookmarker.operations.store_export import (
    export_store,
    plan_import,
    execute_import,
    ImportMode,
    ConflictResolution,
    _dedup_key,
)


class TestDedup:
    def test_same_url_same_path(self):
        """Same URL in same folder should have same key."""
        key1 = _dedup_key("https://example.com", "bookmark_bar")
        key2 = _dedup_key("https://example.com", "bookmark_bar")
        assert key1 == key2

    def test_same_url_different_path(self):
        """Same URL in different folders should have different keys."""
        key1 = _dedup_key("https://example.com", "bookmark_bar")
        key2 = _dedup_key("https://example.com", "other")
        assert key1 != key2

    def test_normalized_urls(self):
        """URLs should be normalized for comparison."""
        key1 = _dedup_key("https://example.com/", "bookmark_bar")
        key2 = _dedup_key("https://example.com", "bookmark_bar")
        assert key1 == key2


class TestExportStore:
    def test_export_creates_valid_json(self, tmp_path, isolate_config):
        """Test that export creates a valid JSON file."""
        store = BookmarkStore()
        store.add(Bookmark(title="Test", url="https://test.com"))

        export_path = tmp_path / "export.json"
        error = export_store(store, export_path)

        assert error is None
        assert export_path.exists()

        # Verify it's valid JSON
        with open(export_path) as f:
            data = json.load(f)

        assert "version" in data
        assert "roots" in data

    def test_export_roundtrip(self, tmp_path, isolate_config):
        """Test that exported file can be reloaded."""
        store = BookmarkStore()
        store.add(Bookmark(title="Example", url="https://example.com"))
        folder = Bookmark(title="Dev", type=BookmarkType.FOLDER)
        store.add(folder)
        store.add(Bookmark(title="GitHub", url="https://github.com"), parent_id=folder.id)

        export_path = tmp_path / "export.json"
        error = export_store(store, export_path)
        assert error is None

        # Load it back
        reloaded = BookmarkStore.load(export_path)

        # Verify structure
        bar = reloaded.roots["bookmark_bar"]
        assert len(bar.children) == 2
        assert bar.children[0].title == "Example"
        assert bar.children[1].title == "Dev"
        assert len(bar.children[1].children) == 1

    def test_export_failure_returns_error(self, tmp_path, isolate_config):
        """Test that export returns error on failure."""
        store = BookmarkStore()
        # Try to write to invalid path
        invalid_path = tmp_path / "nonexistent_dir" / "export.json"
        error = export_store(store, invalid_path)

        assert error is not None
        assert "Failed to export" in error


class TestPlanImport:
    def test_detects_new_bookmarks(self, tmp_path, isolate_config):
        """Test that plan_import identifies new bookmarks to add."""
        # Create an import file with new bookmarks
        import_store = BookmarkStore()
        import_store.add(Bookmark(title="New Site", url="https://newsite.com"))

        import_path = tmp_path / "import.json"
        with open(import_path, "w") as f:
            json.dump(import_store.to_dict(), f)

        # Plan import into empty store
        store = BookmarkStore()
        preview, error = plan_import(store, import_path)

        assert error is None
        assert len(preview.bookmarks_to_add) == 1
        assert preview.bookmarks_to_add[0][0].title == "New Site"
        assert len(preview.conflicts) == 0

    def test_detects_conflicts(self, tmp_path, isolate_config):
        """Test that plan_import identifies conflicts."""
        # Existing store has a bookmark
        store = BookmarkStore()
        store.add(Bookmark(title="Original Title", url="https://example.com"))

        # Import file has same URL with different title
        import_store = BookmarkStore()
        import_store.add(Bookmark(title="New Title", url="https://example.com"))

        import_path = tmp_path / "import.json"
        with open(import_path, "w") as f:
            json.dump(import_store.to_dict(), f)

        preview, error = plan_import(store, import_path)

        assert error is None
        assert len(preview.bookmarks_to_add) == 0
        assert len(preview.conflicts) == 1
        assert preview.conflicts[0].existing_bookmark.title == "Original Title"
        assert preview.conflicts[0].imported_bookmark.title == "New Title"

    def test_skips_identical(self, tmp_path, isolate_config):
        """Test that identical bookmarks are skipped silently."""
        # Same bookmark in both stores
        store = BookmarkStore()
        store.add(Bookmark(title="Same", url="https://same.com"))

        import_store = BookmarkStore()
        import_store.add(Bookmark(title="Same", url="https://same.com"))

        import_path = tmp_path / "import.json"
        with open(import_path, "w") as f:
            json.dump(import_store.to_dict(), f)

        preview, error = plan_import(store, import_path)

        assert error is None
        assert len(preview.bookmarks_to_add) == 0
        assert len(preview.conflicts) == 0

    def test_handles_invalid_json(self, tmp_path, isolate_config):
        """Test that plan_import handles invalid JSON gracefully."""
        import_path = tmp_path / "invalid.json"
        import_path.write_text("not valid json")

        store = BookmarkStore()
        preview, error = plan_import(store, import_path)

        assert error is not None
        assert "Invalid JSON" in error

    def test_detects_new_in_subfolders(self, tmp_path, isolate_config):
        """Test that new bookmarks in subfolders are detected."""
        store = BookmarkStore()

        # Import file has bookmark in subfolder
        import_store = BookmarkStore()
        folder = Bookmark(title="Dev", type=BookmarkType.FOLDER)
        import_store.add(folder)
        import_store.add(Bookmark(title="GitHub", url="https://github.com"), parent_id=folder.id)

        import_path = tmp_path / "import.json"
        with open(import_path, "w") as f:
            json.dump(import_store.to_dict(), f)

        preview, error = plan_import(store, import_path)

        assert error is None
        assert len(preview.bookmarks_to_add) == 1
        assert preview.bookmarks_to_add[0][0].title == "GitHub"
        assert "Dev" in preview.bookmarks_to_add[0][1]


class TestExecuteImport:
    def test_overwrite_replaces_all(self, tmp_path, isolate_config):
        """Test that overwrite mode replaces all bookmarks."""
        # Existing store
        store = BookmarkStore()
        store.add(Bookmark(title="Old", url="https://old.com"))
        store.save()  # Save so backup works

        # Import store
        import_store = BookmarkStore()
        import_store.add(Bookmark(title="New", url="https://new.com"))

        import_path = tmp_path / "import.json"
        with open(import_path, "w") as f:
            json.dump(import_store.to_dict(), f)

        preview, _ = plan_import(store, import_path)
        added, updated, error = execute_import(store, preview, ImportMode.OVERWRITE)

        assert error is None
        # Store should now only have the new bookmark
        all_bm = store.all_bookmarks()
        urls = [b.url for b in all_bm if b.type == BookmarkType.URL]
        assert "https://new.com" in urls
        assert "https://old.com" not in urls

    def test_merge_adds_new(self, tmp_path, isolate_config):
        """Test that merge mode adds new bookmarks."""
        store = BookmarkStore()
        store.add(Bookmark(title="Existing", url="https://existing.com"))
        store.save()

        import_store = BookmarkStore()
        import_store.add(Bookmark(title="New", url="https://new.com"))

        import_path = tmp_path / "import.json"
        with open(import_path, "w") as f:
            json.dump(import_store.to_dict(), f)

        preview, _ = plan_import(store, import_path)
        added, updated, error = execute_import(store, preview, ImportMode.MERGE)

        assert error is None
        assert added == 1
        assert updated == 0

        # Both bookmarks should exist
        all_bm = store.all_bookmarks()
        urls = [b.url for b in all_bm if b.type == BookmarkType.URL]
        assert "https://existing.com" in urls
        assert "https://new.com" in urls

    def test_merge_keep_existing_resolution(self, tmp_path, isolate_config):
        """Test that KEEP_EXISTING resolution is respected."""
        store = BookmarkStore()
        store.add(Bookmark(title="Original Title", url="https://example.com"))
        store.save()

        import_store = BookmarkStore()
        import_store.add(Bookmark(title="New Title", url="https://example.com"))

        import_path = tmp_path / "import.json"
        with open(import_path, "w") as f:
            json.dump(import_store.to_dict(), f)

        preview, _ = plan_import(store, import_path)
        # Set resolution to keep existing
        for conflict in preview.conflicts:
            conflict.resolution = ConflictResolution.KEEP_EXISTING

        added, updated, error = execute_import(store, preview, ImportMode.MERGE)

        assert error is None
        assert updated == 0

        # Title should remain original
        all_bm = store.all_bookmarks()
        example_bm = [b for b in all_bm if "example.com" in b.url][0]
        assert example_bm.title == "Original Title"

    def test_merge_use_imported_resolution(self, tmp_path, isolate_config):
        """Test that USE_IMPORTED resolution is respected."""
        store = BookmarkStore()
        existing = Bookmark(title="Original Title", url="https://example.com")
        store.add(existing)
        store.save()

        import_store = BookmarkStore()
        import_store.add(Bookmark(title="New Title", url="https://example.com"))

        import_path = tmp_path / "import.json"
        with open(import_path, "w") as f:
            json.dump(import_store.to_dict(), f)

        preview, _ = plan_import(store, import_path)
        # Set resolution to use imported
        for conflict in preview.conflicts:
            conflict.resolution = ConflictResolution.USE_IMPORTED

        added, updated, error = execute_import(store, preview, ImportMode.MERGE)

        assert error is None
        assert updated == 1

        # Title should be updated
        all_bm = store.all_bookmarks()
        example_bm = [b for b in all_bm if "example.com" in b.url][0]
        assert example_bm.title == "New Title"

    def test_creates_backup_before_import(self, tmp_path, isolate_config):
        """Test that backup is created before import."""
        store = BookmarkStore()
        store.add(Bookmark(title="Existing", url="https://existing.com"))
        store.save()

        import_store = BookmarkStore()
        import_store.add(Bookmark(title="New", url="https://new.com"))

        import_path = tmp_path / "import.json"
        with open(import_path, "w") as f:
            json.dump(import_store.to_dict(), f)

        # Check no backups exist initially
        backups_dir = isolate_config / "backups"
        initial_backups = list(backups_dir.glob("*.json")) if backups_dir.exists() else []

        preview, _ = plan_import(store, import_path)
        execute_import(store, preview, ImportMode.MERGE)

        # Check backup was created
        backups = list(backups_dir.glob("*.json"))
        assert len(backups) > len(initial_backups)

    def test_creates_missing_folders(self, tmp_path, isolate_config):
        """Test that import creates folder structure as needed."""
        store = BookmarkStore()
        store.save()

        # Import has nested folder structure
        import_store = BookmarkStore()
        folder = Bookmark(title="Dev", type=BookmarkType.FOLDER)
        import_store.add(folder)
        subfolder = Bookmark(title="Python", type=BookmarkType.FOLDER)
        import_store.add(subfolder, parent_id=folder.id)
        import_store.add(
            Bookmark(title="Docs", url="https://docs.python.org"),
            parent_id=subfolder.id
        )

        import_path = tmp_path / "import.json"
        with open(import_path, "w") as f:
            json.dump(import_store.to_dict(), f)

        preview, _ = plan_import(store, import_path)
        added, _, error = execute_import(store, preview, ImportMode.MERGE)

        assert error is None
        assert added == 1

        # Verify folder structure was created
        bar = store.roots["bookmark_bar"]
        dev_folder = [c for c in bar.children if c.title == "Dev"]
        assert len(dev_folder) == 1
        python_folder = [c for c in dev_folder[0].children if c.title == "Python"]
        assert len(python_folder) == 1
        docs_bm = [c for c in python_folder[0].children if c.title == "Docs"]
        assert len(docs_bm) == 1

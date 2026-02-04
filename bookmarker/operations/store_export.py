"""Store export/import operations for JSON file import/export."""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

from ..models.bookmark import Bookmark, BookmarkType, BookmarkStore, normalize_url


class ImportMode(str, Enum):
    """Import mode for JSON import."""
    OVERWRITE = "overwrite"  # Replace entire store
    MERGE = "merge"          # Add new, resolve conflicts


class ConflictResolution(str, Enum):
    """Resolution choice for import conflicts."""
    KEEP_EXISTING = "keep_existing"
    USE_IMPORTED = "use_imported"


@dataclass
class MergeConflict:
    """Represents a conflict between existing and imported bookmarks."""
    existing_bookmark: Bookmark
    imported_bookmark: Bookmark
    folder_path: str
    resolution: Optional[ConflictResolution] = None


@dataclass
class ImportPreview:
    """Preview of what will happen during import."""
    bookmarks_to_add: List[Tuple[Bookmark, str]] = field(default_factory=list)
    conflicts: List[MergeConflict] = field(default_factory=list)
    source_path: Optional[Path] = None


def _dedup_key(url: str, folder_path: str) -> str:
    """Generate a deduplication key: (normalized_url, folder_path)."""
    return f"{normalize_url(url)}|{folder_path}"


def _collect_with_paths(parent: Bookmark, root_name: str, path: str = "") -> List[Tuple[Bookmark, str]]:
    """Collect all URL bookmarks with their folder paths."""
    results = []
    for child in parent.children:
        child_path = f"{path}/{child.title}" if path else child.title
        if child.type == BookmarkType.URL:
            folder_path = f"{root_name}/{path}" if path else root_name
            results.append((child, folder_path))
        elif child.type == BookmarkType.FOLDER:
            results.extend(_collect_with_paths(child, root_name, child_path))
    return results


def _collect_folders_with_paths(parent: Bookmark, root_name: str, path: str = "") -> List[Tuple[Bookmark, str]]:
    """Collect all folders with their paths."""
    results = []
    for child in parent.children:
        if child.type == BookmarkType.FOLDER:
            child_path = f"{path}/{child.title}" if path else child.title
            folder_path = f"{root_name}/{path}" if path else root_name
            results.append((child, folder_path))
            results.extend(_collect_folders_with_paths(child, root_name, child_path))
    return results


def export_store(store: BookmarkStore, path: Path) -> Optional[str]:
    """Export the bookmark store to a JSON file.

    Args:
        store: The BookmarkStore to export
        path: Path to write the JSON file

    Returns:
        Error message or None if successful
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(store.to_dict(), f, indent=2)
        return None
    except Exception as e:
        return f"Failed to export: {e}"


def plan_import(store: BookmarkStore, import_path: Path) -> Tuple[ImportPreview, Optional[str]]:
    """Plan the import by identifying new bookmarks and conflicts.

    Args:
        store: The current BookmarkStore
        import_path: Path to the JSON file to import

    Returns:
        Tuple of (ImportPreview, error_message_or_none)
    """
    preview = ImportPreview(source_path=import_path)

    # Load the import file
    try:
        with open(import_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        import_store = BookmarkStore.from_dict(data)
    except json.JSONDecodeError as e:
        return preview, f"Invalid JSON file: {e}"
    except Exception as e:
        return preview, f"Failed to read import file: {e}"

    # Build index of existing bookmarks by dedup key
    existing_by_key = {}
    for root_name, root in store.roots.items():
        for bm, folder_path in _collect_with_paths(root, root_name):
            key = _dedup_key(bm.url, folder_path)
            existing_by_key[key] = bm

    # Check each bookmark in the import file
    for root_name, root in import_store.roots.items():
        for imported_bm, folder_path in _collect_with_paths(root, root_name):
            key = _dedup_key(imported_bm.url, folder_path)

            if key in existing_by_key:
                existing_bm = existing_by_key[key]
                # Same URL in same folder - check if titles differ
                if existing_bm.title != imported_bm.title:
                    # Conflict: same URL, same folder, different title
                    preview.conflicts.append(MergeConflict(
                        existing_bookmark=existing_bm,
                        imported_bookmark=imported_bm,
                        folder_path=folder_path,
                    ))
                # If titles are the same, it's identical - skip silently
            else:
                # New bookmark to add
                preview.bookmarks_to_add.append((imported_bm, folder_path))

    return preview, None


def _ensure_folder_path(store: BookmarkStore, folder_path: str) -> Optional[Bookmark]:
    """Ensure a folder path exists in the store, creating folders as needed.

    Args:
        store: The BookmarkStore
        folder_path: Path like "bookmark_bar/Dev/Python"

    Returns:
        The folder Bookmark at that path, or None if invalid
    """
    parts = folder_path.split("/")
    if not parts:
        return None

    root_name = parts[0]
    root = store.roots.get(root_name)
    if not root:
        return None

    current = root
    for folder_name in parts[1:]:
        # Find or create the subfolder
        found = None
        for child in current.children:
            if child.type == BookmarkType.FOLDER and child.title == folder_name:
                found = child
                break

        if found is None:
            # Create the folder
            new_folder = Bookmark(
                type=BookmarkType.FOLDER,
                title=folder_name,
            )
            store.add(new_folder, parent_id=current.id)
            found = new_folder

        current = found

    return current


def execute_import(
    store: BookmarkStore,
    preview: ImportPreview,
    mode: ImportMode
) -> Tuple[int, int, Optional[str]]:
    """Execute the import based on the preview.

    Args:
        store: The BookmarkStore to import into
        preview: The ImportPreview from plan_import
        mode: OVERWRITE or MERGE

    Returns:
        Tuple of (added_count, updated_count, error_message_or_none)
    """
    # Create backup before any changes
    try:
        store.backup()
    except Exception as e:
        return 0, 0, f"Failed to create backup: {e}"

    if mode == ImportMode.OVERWRITE:
        # Load the import file and replace the entire store
        try:
            with open(preview.source_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            import_store = BookmarkStore.from_dict(data)

            # Count bookmarks in import
            total = 0
            for root in import_store.roots.values():
                for _ in _collect_with_paths(root, ""):
                    total += 1

            # Replace store contents
            store.roots = import_store.roots
            store.version = import_store.version
            store.last_modified = import_store.last_modified

            return total, 0, None
        except Exception as e:
            return 0, 0, f"Failed to import: {e}"

    # MERGE mode
    added = 0
    updated = 0

    # Add new bookmarks
    for imported_bm, folder_path in preview.bookmarks_to_add:
        parent = _ensure_folder_path(store, folder_path)
        if parent:
            new_bm = Bookmark(
                type=BookmarkType.URL,
                title=imported_bm.title,
                url=imported_bm.url,
                date_added=imported_bm.date_added,
                date_modified=imported_bm.date_modified,
                preferred_browser=imported_bm.preferred_browser,
            )
            store.add(new_bm, parent_id=parent.id)
            added += 1

    # Handle conflicts based on resolutions
    for conflict in preview.conflicts:
        if conflict.resolution == ConflictResolution.USE_IMPORTED:
            # Update the existing bookmark with imported data
            existing = store.find_by_id(conflict.existing_bookmark.id)
            if existing:
                existing.title = conflict.imported_bookmark.title
                existing.date_modified = conflict.imported_bookmark.date_modified
                if conflict.imported_bookmark.preferred_browser:
                    existing.preferred_browser = conflict.imported_bookmark.preferred_browser
                updated += 1
        # KEEP_EXISTING or None: do nothing

    return added, updated, None

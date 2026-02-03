"""Import orchestrator - imports bookmarks from browsers into the store."""

from typing import List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from ..models.bookmark import Bookmark, BookmarkType, BookmarkStore, normalize_url
from .chrome import read_chrome_bookmarks
from .edge import read_edge_bookmarks
from .firefox import read_firefox_bookmarks


def _dedup_key(bookmark: Bookmark, parent_path: str) -> str:
    """Generate a deduplication key: (normalized_url, parent_folder_path)."""
    return f"{normalize_url(bookmark.url)}|{parent_path}"


def _get_parent_path(bookmark: Bookmark, root_name: str, parent_title: str = "") -> str:
    """Build a simple parent path string."""
    return f"{root_name}/{parent_title}" if parent_title else root_name


def _collect_with_paths(parent: Bookmark, root_name: str, path: str = "") -> list:
    """Collect all URL bookmarks with their folder paths."""
    results = []
    for child in parent.children:
        child_path = f"{path}/{child.title}" if path else child.title
        if child.type == BookmarkType.URL:
            results.append((child, f"{root_name}/{path}" if path else root_name))
        elif child.type == BookmarkType.FOLDER:
            results.extend(_collect_with_paths(child, root_name, child_path))
    return results


def import_from_browser(browser_name: str, store: BookmarkStore,
                        bookmark_path=None) -> tuple:
    """Import bookmarks from a browser into the store.

    New bookmarks are added; existing ones (by dedup key) are skipped.

    Args:
        browser_name: "chrome", "edge", or "firefox"
        store: The target BookmarkStore
        bookmark_path: Optional explicit path to bookmark file

    Returns:
        Tuple of (added_count, skipped_count, error_message_or_none)
    """
    # Read from browser
    if browser_name == "chrome":
        browser_store = read_chrome_bookmarks(bookmark_path)
    elif browser_name == "edge":
        browser_store = read_edge_bookmarks(bookmark_path)
    elif browser_name == "firefox":
        browser_store = read_firefox_bookmarks(bookmark_path)
    else:
        return 0, 0, f"Unknown browser: {browser_name}"

    if browser_store is None:
        return 0, 0, f"Could not read bookmarks from {browser_name}"

    # Build dedup set from existing store
    existing_keys = set()
    for root_name, root in store.roots.items():
        for bm, path in _collect_with_paths(root, root_name):
            existing_keys.add(_dedup_key(bm, path))

    added = 0
    skipped = 0

    # Import each root
    for root_name in ["bookmark_bar", "other"]:
        browser_root = browser_store.roots.get(root_name)
        if not browser_root:
            continue
        store_root = store.roots.get(root_name)
        if not store_root:
            continue

        a, s = _import_children(browser_root.children, store_root, store,
                                root_name, existing_keys, browser_name)
        added += a
        skipped += s

    return added, skipped, None


def _import_children(browser_children: list, store_parent: Bookmark,
                     store: BookmarkStore, root_name: str,
                     existing_keys: set, browser_name: str,
                     parent_path: str = "") -> tuple:
    """Recursively import children from browser into store parent."""
    added = 0
    skipped = 0

    for browser_bm in browser_children:
        if browser_bm.type == BookmarkType.FOLDER:
            # Find or create matching folder in store
            existing_folder = None
            for child in store_parent.children:
                if child.type == BookmarkType.FOLDER and child.title == browser_bm.title:
                    existing_folder = child
                    break

            if existing_folder is None:
                new_folder = Bookmark(
                    type=BookmarkType.FOLDER,
                    title=browser_bm.title,
                    date_added=browser_bm.date_added,
                    date_modified=browser_bm.date_modified,
                    source_browser=browser_name,
                    source_id=browser_bm.source_id,
                )
                store.add(new_folder, parent_id=store_parent.id)
                existing_folder = new_folder
                added += 1

            child_path = f"{parent_path}/{browser_bm.title}" if parent_path else browser_bm.title
            a, s = _import_children(browser_bm.children, existing_folder, store,
                                    root_name, existing_keys, browser_name, child_path)
            added += a
            skipped += s

        elif browser_bm.type == BookmarkType.URL:
            key = _dedup_key(browser_bm, f"{root_name}/{parent_path}" if parent_path else root_name)
            if key in existing_keys:
                skipped += 1
            else:
                new_bm = Bookmark(
                    type=BookmarkType.URL,
                    title=browser_bm.title,
                    url=browser_bm.url,
                    date_added=browser_bm.date_added,
                    date_modified=browser_bm.date_modified,
                    source_browser=browser_name,
                    source_id=browser_bm.source_id,
                )
                store.add(new_bm, parent_id=store_parent.id)
                existing_keys.add(key)
                added += 1

    return added, skipped


class ImportWorker(QThread):
    """Worker thread for importing bookmarks from browsers."""

    progress = pyqtSignal(str)  # Status message
    finished_import = pyqtSignal(int, int, str)  # added, skipped, error

    def __init__(self, browsers: List[str], store: BookmarkStore, parent=None):
        super().__init__(parent)
        self.browsers = browsers
        self.store = store

    def run(self):
        total_added = 0
        total_skipped = 0
        errors = []

        for browser in self.browsers:
            self.progress.emit(f"Importing from {browser}...")
            added, skipped, error = import_from_browser(browser, self.store)
            total_added += added
            total_skipped += skipped
            if error:
                errors.append(error)

        error_msg = "; ".join(errors) if errors else ""
        self.finished_import.emit(total_added, total_skipped, error_msg)

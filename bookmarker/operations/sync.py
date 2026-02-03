"""Bidirectional sync engine.

Sync = import new items from browser + push store items to browser.
Deletion is additive-only: missing items are added, never deleted.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from ..models.bookmark import Bookmark, BookmarkType, BookmarkStore, normalize_url
from .chrome import read_chrome_bookmarks, write_chrome_bookmarks
from .edge import read_edge_bookmarks, write_edge_bookmarks
from .firefox import read_firefox_bookmarks, write_firefox_bookmarks
from .browser_detect import is_browser_running, CHROME_PROCESS_NAMES, EDGE_PROCESS_NAMES, FIREFOX_PROCESS_NAMES


class SyncActionType(str, Enum):
    ADD_TO_STORE = "add_to_store"
    UPDATE_STORE = "update_store"
    ADD_TO_BROWSER = "add_to_browser"
    UPDATE_BROWSER = "update_browser"


@dataclass
class SyncAction:
    action: SyncActionType
    bookmark: Bookmark
    root_name: str
    parent_title: str = ""
    description: str = ""


def _read_browser(browser_name: str, bookmark_path=None) -> Optional[BookmarkStore]:
    """Read bookmarks from the given browser."""
    if browser_name == "chrome":
        return read_chrome_bookmarks(bookmark_path)
    elif browser_name == "edge":
        return read_edge_bookmarks(bookmark_path)
    elif browser_name == "firefox":
        return read_firefox_bookmarks(bookmark_path)
    return None


def _write_browser(browser_name: str, store: BookmarkStore, bookmark_path=None) -> bool:
    """Write bookmarks to the given browser."""
    if browser_name == "chrome":
        return write_chrome_bookmarks(store, bookmark_path)
    elif browser_name == "edge":
        return write_edge_bookmarks(store, bookmark_path)
    elif browser_name == "firefox":
        return write_firefox_bookmarks(store, bookmark_path)
    return False


def _collect_url_bookmarks(parent: Bookmark, root_name: str,
                           path: str = "") -> list:
    """Collect (bookmark, root_name, path) tuples for all URL bookmarks."""
    results = []
    for child in parent.children:
        if child.type == BookmarkType.URL:
            results.append((child, root_name, path))
        elif child.type == BookmarkType.FOLDER:
            child_path = f"{path}/{child.title}" if path else child.title
            results.extend(_collect_url_bookmarks(child, root_name, child_path))
    return results


def _build_lookup(store: BookmarkStore) -> dict:
    """Build a lookup: (normalized_url, root_name, parent_path) -> Bookmark."""
    lookup = {}
    for root_name, root in store.roots.items():
        for bm, rn, path in _collect_url_bookmarks(root, root_name):
            key = (normalize_url(bm.url), rn, path)
            lookup[key] = bm
    return lookup


def _build_source_lookup(store: BookmarkStore) -> dict:
    """Build a lookup: (source_browser, source_id) -> Bookmark."""
    lookup = {}
    for bm in store.all_bookmarks():
        if bm.source_browser and bm.source_id:
            lookup[(bm.source_browser, bm.source_id)] = bm
    return lookup


def plan_sync(store: BookmarkStore, browser_name: str,
              bookmark_path=None) -> tuple:
    """Plan sync actions between store and browser.

    Returns:
        Tuple of (actions: List[SyncAction], browser_store: BookmarkStore, error: str)
    """
    browser_store = _read_browser(browser_name, bookmark_path)
    if browser_store is None:
        return [], None, f"Could not read bookmarks from {browser_name}"

    actions = []

    store_lookup = _build_lookup(store)
    browser_lookup = _build_lookup(browser_store)
    store_source_lookup = _build_source_lookup(store)

    # For each browser bookmark not in store: add_to_store
    for key, browser_bm in browser_lookup.items():
        norm_url, root_name, path = key
        # Check by source ID first
        existing = None
        if browser_bm.source_id:
            existing = store_source_lookup.get((browser_name, browser_bm.source_id))

        if existing is None:
            existing = store_lookup.get(key)

        if existing is None:
            actions.append(SyncAction(
                action=SyncActionType.ADD_TO_STORE,
                bookmark=browser_bm,
                root_name=root_name,
                parent_title=path,
                description=f"Add '{browser_bm.title}' to store from {browser_name}",
            ))
        else:
            # Check if browser version is newer
            try:
                browser_mod = datetime.fromisoformat(browser_bm.date_modified)
                store_mod = datetime.fromisoformat(existing.date_modified)
                if browser_mod > store_mod:
                    actions.append(SyncAction(
                        action=SyncActionType.UPDATE_STORE,
                        bookmark=browser_bm,
                        root_name=root_name,
                        parent_title=path,
                        description=f"Update '{browser_bm.title}' in store (newer in {browser_name})",
                    ))
            except (ValueError, TypeError):
                pass

    # For each store bookmark not in browser: add_to_browser
    for key, store_bm in store_lookup.items():
        norm_url, root_name, path = key
        if key not in browser_lookup:
            actions.append(SyncAction(
                action=SyncActionType.ADD_TO_BROWSER,
                bookmark=store_bm,
                root_name=root_name,
                parent_title=path,
                description=f"Add '{store_bm.title}' to {browser_name} from store",
            ))

    return actions, browser_store, None


def execute_sync(store: BookmarkStore, browser_name: str,
                 actions: List[SyncAction],
                 bookmark_path=None) -> tuple:
    """Execute approved sync actions.

    Args:
        store: The BookmarkStore (modified in place for store changes)
        browser_name: Target browser name
        actions: List of approved SyncActions
        bookmark_path: Optional explicit browser bookmark path

    Returns:
        Tuple of (store_changes: int, browser_changes: int, error: str)
    """
    store_changes = 0
    browser_needs_write = False

    for action in actions:
        if action.action == SyncActionType.ADD_TO_STORE:
            new_bm = Bookmark(
                type=action.bookmark.type,
                title=action.bookmark.title,
                url=action.bookmark.url,
                date_added=action.bookmark.date_added,
                date_modified=action.bookmark.date_modified,
                source_browser=browser_name,
                source_id=action.bookmark.source_id,
            )
            _add_to_store_at_path(store, new_bm, action.root_name, action.parent_title)
            store_changes += 1

        elif action.action == SyncActionType.UPDATE_STORE:
            existing = store.find_by_url(action.bookmark.url)
            if existing:
                target = existing[0]
                target.title = action.bookmark.title
                target.date_modified = action.bookmark.date_modified
                store_changes += 1

        elif action.action in (SyncActionType.ADD_TO_BROWSER, SyncActionType.UPDATE_BROWSER):
            browser_needs_write = True

    # Write browser changes (push entire store)
    browser_changes = 0
    error = None
    if browser_needs_write:
        process_map = {
            "chrome": CHROME_PROCESS_NAMES,
            "edge": EDGE_PROCESS_NAMES,
            "firefox": FIREFOX_PROCESS_NAMES,
        }
        procs = process_map.get(browser_name, [])
        if is_browser_running(procs):
            error = f"{browser_name} is running. Browser changes not applied."
        else:
            success = _write_browser(browser_name, store, bookmark_path)
            if success:
                browser_changes = sum(
                    1 for a in actions
                    if a.action in (SyncActionType.ADD_TO_BROWSER, SyncActionType.UPDATE_BROWSER)
                )
            else:
                error = f"Failed to write to {browser_name}"

    # Save store
    if store_changes > 0:
        store.save()

    return store_changes, browser_changes, error


def _add_to_store_at_path(store: BookmarkStore, bookmark: Bookmark,
                          root_name: str, parent_path: str) -> None:
    """Add a bookmark to the store at the specified folder path, creating folders as needed."""
    root = store.roots.get(root_name)
    if not root:
        return

    if not parent_path:
        store.add(bookmark, parent_id=root.id)
        return

    # Navigate/create folder path
    parts = parent_path.split("/")
    current = root
    for part in parts:
        found = None
        for child in current.children:
            if child.type == BookmarkType.FOLDER and child.title == part:
                found = child
                break
        if found is None:
            new_folder = Bookmark(type=BookmarkType.FOLDER, title=part)
            store.add(new_folder, parent_id=current.id)
            found = new_folder
        current = found

    store.add(bookmark, parent_id=current.id)


class SyncWorker(QThread):
    """Worker thread for sync operations."""

    progress = pyqtSignal(str)
    sync_planned = pyqtSignal(list)  # List of SyncAction
    finished_sync = pyqtSignal(int, int, str)  # store_changes, browser_changes, error

    def __init__(self, browser_name: str, store: BookmarkStore,
                 approved_actions: Optional[List[SyncAction]] = None,
                 bookmark_path=None, parent=None):
        super().__init__(parent)
        self.browser_name = browser_name
        self.store = store
        self.approved_actions = approved_actions
        self.bookmark_path = bookmark_path

    def run(self):
        if self.approved_actions is None:
            # Planning phase
            self.progress.emit(f"Reading {self.browser_name} bookmarks...")
            actions, _, error = plan_sync(self.store, self.browser_name, self.bookmark_path)
            if error:
                self.finished_sync.emit(0, 0, error)
                return
            self.sync_planned.emit(actions)
        else:
            # Execution phase
            self.progress.emit("Applying sync changes...")
            store_changes, browser_changes, error = execute_sync(
                self.store, self.browser_name, self.approved_actions, self.bookmark_path
            )
            self.finished_sync.emit(store_changes, browser_changes, error or "")

"""Chrome bookmark reader/writer with checksum calculation."""

import json
import shutil
from datetime import datetime, timezone
from hashlib import md5
from pathlib import Path
from typing import List, Optional

from ..models.bookmark import Bookmark, BookmarkType, BookmarkStore
from ..utils.config import get_backups_dir
from .browser_detect import get_browser, is_browser_running, CHROME_PROCESS_NAMES

# Chrome epoch: Jan 1, 1601 (Windows FILETIME)
# Difference from Unix epoch in microseconds
_CHROME_EPOCH_DELTA = 11644473600 * 1000000


def chrome_time_to_iso(chrome_time: str) -> str:
    """Convert Chrome's microsecond timestamp to ISO 8601."""
    try:
        us = int(chrome_time)
        if us == 0:
            return datetime.now().isoformat()
        unix_us = us - _CHROME_EPOCH_DELTA
        dt = datetime.fromtimestamp(unix_us / 1000000, tz=timezone.utc)
        return dt.isoformat()
    except (ValueError, OSError):
        return datetime.now().isoformat()


def iso_to_chrome_time(iso_str: str) -> str:
    """Convert ISO 8601 to Chrome's microsecond timestamp."""
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        unix_us = int(dt.timestamp() * 1000000)
        chrome_us = unix_us + _CHROME_EPOCH_DELTA
        return str(chrome_us)
    except (ValueError, OSError):
        return "0"


def calculate_checksum(roots: dict) -> str:
    """Calculate the MD5 checksum for Chrome bookmark roots.

    This mirrors Chromium's bookmark_codec.cc algorithm:
    For each node, hash id (ascii), name (UTF-16-LE), type, and url (ascii for URLs).
    Process bookmark_bar, other, synced in order.
    """
    digest = md5()

    def digest_url(node: dict) -> None:
        digest.update(node["id"].encode("ascii"))
        digest.update(node["name"].encode("UTF-16-LE"))
        digest.update(b"url")
        digest.update(node["url"].encode("ascii"))

    def digest_folder(node: dict) -> None:
        digest.update(node["id"].encode("ascii"))
        digest.update(node["name"].encode("UTF-16-LE"))
        digest.update(b"folder")
        for child in node.get("children", []):
            update_digest(child)

    def update_digest(node: dict) -> None:
        node_type = node.get("type", "url")
        if node_type == "folder":
            digest_folder(node)
        else:
            digest_url(node)

    update_digest(roots["bookmark_bar"])
    update_digest(roots["other"])
    update_digest(roots["synced"])

    return digest.hexdigest()


def _parse_chrome_node(node: dict, source_browser: str = "chrome") -> Bookmark:
    """Convert a Chrome JSON node to a Bookmark."""
    node_type = node.get("type", "url")
    children = []
    if node_type == "folder":
        for child in node.get("children", []):
            children.append(_parse_chrome_node(child, source_browser))

    return Bookmark(
        type=BookmarkType.FOLDER if node_type == "folder" else BookmarkType.URL,
        title=node.get("name", ""),
        url=node.get("url", ""),
        position=0,
        date_added=chrome_time_to_iso(node.get("date_added", "0")),
        date_modified=chrome_time_to_iso(node.get("date_modified", "0")),
        source_browser=source_browser,
        source_id=node.get("id", ""),
        children=children,
    )


def _bookmark_to_chrome_node(bookmark: Bookmark, id_counter: list) -> dict:
    """Convert a Bookmark to a Chrome JSON node."""
    node_id = str(id_counter[0])
    id_counter[0] += 1

    node = {
        "date_added": iso_to_chrome_time(bookmark.date_added),
        "date_last_used": "0",
        "guid": f"00000000-0000-4000-0000-{node_id.zfill(12)}",
        "id": node_id,
        "name": bookmark.title,
        "type": "folder" if bookmark.type == BookmarkType.FOLDER else "url",
    }

    if bookmark.type == BookmarkType.URL:
        node["url"] = bookmark.url
    else:
        node["date_modified"] = iso_to_chrome_time(bookmark.date_modified)
        node["children"] = [
            _bookmark_to_chrome_node(child, id_counter)
            for child in bookmark.children
        ]

    return node


def read_chrome_bookmarks(bookmark_path: Optional[Path] = None,
                          source_browser: str = "chrome") -> Optional[BookmarkStore]:
    """Read bookmarks from Chrome's JSON file into a BookmarkStore.

    Args:
        bookmark_path: Path to the Chrome Bookmarks file. Auto-detected if None.
        source_browser: Source browser name for provenance tracking.

    Returns:
        BookmarkStore with imported bookmarks, or None on error.
    """
    if bookmark_path is None:
        browser = get_browser(source_browser)
        if not browser or not browser.bookmark_path:
            return None
        bookmark_path = browser.bookmark_path

    try:
        with open(bookmark_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    roots = data.get("roots", {})
    store = BookmarkStore()

    # Parse bookmark_bar
    if "bookmark_bar" in roots:
        parsed = _parse_chrome_node(roots["bookmark_bar"], source_browser)
        store.roots["bookmark_bar"].children = parsed.children
        # Set parent_ids
        _set_parent_ids(store.roots["bookmark_bar"])

    # Parse other
    if "other" in roots:
        parsed = _parse_chrome_node(roots["other"], source_browser)
        store.roots["other"].children = parsed.children
        _set_parent_ids(store.roots["other"])

    return store


def _set_parent_ids(parent: Bookmark) -> None:
    """Recursively set parent_id on children."""
    for i, child in enumerate(parent.children):
        child.parent_id = parent.id
        child.position = i
        if child.type == BookmarkType.FOLDER:
            _set_parent_ids(child)


def write_chrome_bookmarks(store: BookmarkStore,
                           bookmark_path: Optional[Path] = None,
                           source_browser: str = "chrome") -> bool:
    """Write a BookmarkStore to Chrome's JSON format.

    The browser must be closed. Creates a backup first.

    Args:
        store: The BookmarkStore to write.
        bookmark_path: Path to the Chrome Bookmarks file. Auto-detected if None.
        source_browser: Browser name for path detection.

    Returns:
        True if successful, False otherwise.
    """
    process_names = CHROME_PROCESS_NAMES
    if source_browser == "edge":
        from .browser_detect import EDGE_PROCESS_NAMES
        process_names = EDGE_PROCESS_NAMES

    if is_browser_running(process_names):
        return False

    if bookmark_path is None:
        browser = get_browser(source_browser)
        if not browser or not browser.bookmark_path:
            return False
        bookmark_path = browser.bookmark_path

    # Backup existing file
    if bookmark_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = get_backups_dir() / f"{source_browser}_bookmarks_{timestamp}.json"
        shutil.copy2(bookmark_path, backup_path)

    # Build Chrome JSON structure
    id_counter = [1]

    bar_children = [
        _bookmark_to_chrome_node(child, id_counter)
        for child in store.roots.get("bookmark_bar", Bookmark(type=BookmarkType.FOLDER)).children
    ]
    other_children = [
        _bookmark_to_chrome_node(child, id_counter)
        for child in store.roots.get("other", Bookmark(type=BookmarkType.FOLDER)).children
    ]

    now_chrome = iso_to_chrome_time(datetime.now().isoformat())

    chrome_data = {
        "checksum": "",
        "roots": {
            "bookmark_bar": {
                "children": bar_children,
                "date_added": now_chrome,
                "date_modified": now_chrome,
                "guid": "00000000-0000-4000-0000-000000000000",
                "id": "0",
                "name": "Bookmarks bar",
                "type": "folder",
            },
            "other": {
                "children": other_children,
                "date_added": now_chrome,
                "date_modified": now_chrome,
                "guid": "00000000-0000-4000-0000-000000000001",
                "id": str(id_counter[0]),
                "name": "Other bookmarks",
                "type": "folder",
            },
            "synced": {
                "children": [],
                "date_added": now_chrome,
                "date_modified": "0",
                "guid": "00000000-0000-4000-0000-000000000002",
                "id": str(id_counter[0] + 1),
                "name": "Mobile bookmarks",
                "type": "folder",
            },
        },
        "version": 1,
    }

    # Calculate and set checksum
    chrome_data["checksum"] = calculate_checksum(chrome_data["roots"])

    try:
        with open(bookmark_path, "w", encoding="utf-8") as f:
            json.dump(chrome_data, f, indent=3)
        return True
    except OSError:
        return False

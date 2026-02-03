"""Firefox bookmark reader/writer using SQLite."""

import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..models.bookmark import Bookmark, BookmarkType, BookmarkStore
from ..utils.config import get_backups_dir
from .browser_detect import get_browser, is_browser_running, FIREFOX_PROCESS_NAMES

# Firefox bookmark type constants
_MOZ_TYPE_BOOKMARK = 1
_MOZ_TYPE_FOLDER = 2
_MOZ_TYPE_SEPARATOR = 3

# Firefox root folder IDs
_MOZ_ROOT_ID = 1
_MOZ_MENU_ID = 2         # Bookmarks Menu
_MOZ_TOOLBAR_ID = 3      # Bookmarks Toolbar
_MOZ_UNFILED_ID = 5      # Other Bookmarks
_MOZ_MOBILE_ID = 6       # Mobile Bookmarks


def _firefox_time_to_iso(moz_time: int) -> str:
    """Convert Firefox's microsecond timestamp to ISO 8601."""
    try:
        if moz_time == 0:
            return datetime.now().isoformat()
        dt = datetime.fromtimestamp(moz_time / 1000000, tz=timezone.utc)
        return dt.isoformat()
    except (ValueError, OSError):
        return datetime.now().isoformat()


def _iso_to_firefox_time(iso_str: str) -> int:
    """Convert ISO 8601 to Firefox's microsecond timestamp."""
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000000)
    except (ValueError, OSError):
        return int(datetime.now().timestamp() * 1000000)


def _safe_copy_db(places_path: Path) -> Optional[Path]:
    """Safely copy the Firefox places.sqlite using sqlite3 backup API.

    This works even while Firefox is running.
    """
    tmp_dir = tempfile.mkdtemp()
    dest = Path(tmp_dir) / "places_copy.sqlite"

    try:
        source_conn = sqlite3.connect(f"file:{places_path}?mode=ro", uri=True)
        dest_conn = sqlite3.connect(str(dest))
        source_conn.backup(dest_conn)
        source_conn.close()
        dest_conn.close()
        return dest
    except sqlite3.Error:
        return None


def _read_bookmarks_from_db(db_path: Path, source_browser: str = "firefox") -> Optional[BookmarkStore]:
    """Read bookmarks from a Firefox places.sqlite database."""
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all bookmarks with their URLs
        cursor.execute("""
            SELECT b.id, b.type, b.title, b.parent, b.position,
                   b.dateAdded, b.lastModified,
                   p.url
            FROM moz_bookmarks b
            LEFT JOIN moz_places p ON b.fk = p.id
            WHERE b.type IN (?, ?)
            ORDER BY b.parent, b.position
        """, (_MOZ_TYPE_BOOKMARK, _MOZ_TYPE_FOLDER))

        rows = cursor.fetchall()
        conn.close()

        # Build lookup: parent_id -> list of children
        children_map: dict[int, list] = {}
        node_map: dict[int, dict] = {}

        for row in rows:
            node = {
                "id": row["id"],
                "type": row["type"],
                "title": row["title"] or "",
                "parent": row["parent"],
                "position": row["position"],
                "date_added": row["dateAdded"] or 0,
                "date_modified": row["lastModified"] or 0,
                "url": row["url"] or "",
            }
            node_map[row["id"]] = node
            parent = row["parent"]
            if parent not in children_map:
                children_map[parent] = []
            children_map[parent].append(node)

        def build_bookmark(node: dict) -> Bookmark:
            is_folder = node["type"] == _MOZ_TYPE_FOLDER
            children = []
            if is_folder and node["id"] in children_map:
                for child_node in children_map[node["id"]]:
                    children.append(build_bookmark(child_node))

            return Bookmark(
                type=BookmarkType.FOLDER if is_folder else BookmarkType.URL,
                title=node["title"],
                url=node["url"] if not is_folder else "",
                position=node["position"],
                date_added=_firefox_time_to_iso(node["date_added"]),
                date_modified=_firefox_time_to_iso(node["date_modified"]),
                source_browser=source_browser,
                source_id=str(node["id"]),
                children=children,
            )

        store = BookmarkStore()

        # Toolbar -> bookmark_bar
        if _MOZ_TOOLBAR_ID in children_map:
            for node in children_map[_MOZ_TOOLBAR_ID]:
                bm = build_bookmark(node)
                bm.parent_id = store.roots["bookmark_bar"].id
                store.roots["bookmark_bar"].children.append(bm)

        # Menu + Unfiled -> other
        for root_id in [_MOZ_MENU_ID, _MOZ_UNFILED_ID]:
            if root_id in children_map:
                for node in children_map[root_id]:
                    bm = build_bookmark(node)
                    bm.parent_id = store.roots["other"].id
                    store.roots["other"].children.append(bm)

        # Set positions
        for i, c in enumerate(store.roots["bookmark_bar"].children):
            c.position = i
        for i, c in enumerate(store.roots["other"].children):
            c.position = i

        return store

    except sqlite3.Error:
        return None


def read_firefox_bookmarks(places_path: Optional[Path] = None) -> Optional[BookmarkStore]:
    """Read bookmarks from Firefox's places.sqlite.

    Uses sqlite3 backup API for safe reading even while Firefox runs.

    Args:
        places_path: Path to places.sqlite. Auto-detected if None.

    Returns:
        BookmarkStore with imported bookmarks, or None on error.
    """
    if places_path is None:
        browser = get_browser("firefox")
        if not browser or not browser.bookmark_path:
            return None
        places_path = browser.bookmark_path

    if not places_path.exists():
        return None

    # Safe copy via backup API
    copy_path = _safe_copy_db(places_path)
    if not copy_path:
        return None

    try:
        store = _read_bookmarks_from_db(copy_path)
        return store
    finally:
        # Clean up temp copy
        shutil.rmtree(copy_path.parent, ignore_errors=True)


def write_firefox_bookmarks(store: BookmarkStore,
                            places_path: Optional[Path] = None) -> bool:
    """Write a BookmarkStore to Firefox's places.sqlite.

    Firefox must be closed for this operation.

    Args:
        store: The BookmarkStore to write.
        places_path: Path to places.sqlite. Auto-detected if None.

    Returns:
        True if successful, False otherwise.
    """
    if is_browser_running(FIREFOX_PROCESS_NAMES):
        return False

    if places_path is None:
        browser = get_browser("firefox")
        if not browser or not browser.bookmark_path:
            return False
        places_path = browser.bookmark_path

    if not places_path.exists():
        return False

    # Backup existing database
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = get_backups_dir() / f"firefox_places_{timestamp}.sqlite"
    shutil.copy2(places_path, backup_path)

    try:
        conn = sqlite3.connect(str(places_path))
        cursor = conn.cursor()

        # Clear existing bookmarks (keep root folders)
        cursor.execute("""
            DELETE FROM moz_bookmarks
            WHERE id NOT IN (?, ?, ?, ?, ?)
            AND type IN (?, ?)
        """, (_MOZ_ROOT_ID, _MOZ_MENU_ID, _MOZ_TOOLBAR_ID, _MOZ_UNFILED_ID, _MOZ_MOBILE_ID,
              _MOZ_TYPE_BOOKMARK, _MOZ_TYPE_FOLDER))

        # Get next available ID
        cursor.execute("SELECT MAX(id) FROM moz_bookmarks")
        max_id = cursor.fetchone()[0] or _MOZ_MOBILE_ID
        next_id = [max_id + 1]

        def ensure_url(url: str) -> int:
            """Insert URL into moz_places if not exists, return place ID."""
            cursor.execute("SELECT id FROM moz_places WHERE url = ?", (url,))
            row = cursor.fetchone()
            if row:
                return row[0]
            cursor.execute(
                "INSERT INTO moz_places (url, title, rev_host, visit_count, hidden, typed, frecency, last_visit_date) "
                "VALUES (?, '', ?, 0, 0, 0, -1, NULL)",
                (url, _reverse_host(url)),
            )
            return cursor.lastrowid

        def insert_bookmark(bm: Bookmark, parent_id: int, position: int) -> None:
            bm_id = next_id[0]
            next_id[0] += 1

            if bm.type == BookmarkType.URL:
                place_id = ensure_url(bm.url)
                cursor.execute(
                    "INSERT INTO moz_bookmarks (id, type, fk, parent, position, title, dateAdded, lastModified) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (bm_id, _MOZ_TYPE_BOOKMARK, place_id, parent_id, position,
                     bm.title, _iso_to_firefox_time(bm.date_added),
                     _iso_to_firefox_time(bm.date_modified)),
                )
            else:
                cursor.execute(
                    "INSERT INTO moz_bookmarks (id, type, fk, parent, position, title, dateAdded, lastModified) "
                    "VALUES (?, ?, NULL, ?, ?, ?, ?, ?)",
                    (bm_id, _MOZ_TYPE_FOLDER, parent_id, position,
                     bm.title, _iso_to_firefox_time(bm.date_added),
                     _iso_to_firefox_time(bm.date_modified)),
                )
                for i, child in enumerate(bm.children):
                    insert_bookmark(child, bm_id, i)

        # Write bookmark_bar -> toolbar
        for i, bm in enumerate(store.roots.get("bookmark_bar", Bookmark(type=BookmarkType.FOLDER)).children):
            insert_bookmark(bm, _MOZ_TOOLBAR_ID, i)

        # Write other -> unfiled
        for i, bm in enumerate(store.roots.get("other", Bookmark(type=BookmarkType.FOLDER)).children):
            insert_bookmark(bm, _MOZ_UNFILED_ID, i)

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error:
        return False


def _reverse_host(url: str) -> str:
    """Create Firefox-style reversed host string."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if host:
            return "." + ".".join(reversed(host.split("."))) + "."
    except Exception:
        pass
    return ""

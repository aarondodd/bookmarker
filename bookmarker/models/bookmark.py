"""Bookmark data model and store."""

import json
import shutil
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict
from urllib.parse import urlparse

from ..utils.config import get_bookmarks_file, get_backups_dir


class BookmarkType(str, Enum):
    URL = "url"
    FOLDER = "folder"


@dataclass
class Bookmark:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: BookmarkType = BookmarkType.URL
    title: str = ""
    url: str = ""
    parent_id: Optional[str] = None
    position: int = 0
    date_added: str = field(default_factory=lambda: datetime.now().isoformat())
    date_modified: str = field(default_factory=lambda: datetime.now().isoformat())
    preferred_browser: Optional[str] = None
    source_browser: Optional[str] = None
    source_id: Optional[str] = None
    children: List["Bookmark"] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, BookmarkType) else self.type,
            "title": self.title,
            "url": self.url,
            "parent_id": self.parent_id,
            "position": self.position,
            "date_added": self.date_added,
            "date_modified": self.date_modified,
            "preferred_browser": self.preferred_browser,
            "source_browser": self.source_browser,
            "source_id": self.source_id,
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Bookmark":
        """Create a Bookmark from a dictionary."""
        children = [cls.from_dict(c) for c in data.get("children", [])]
        btype = data.get("type", "url")
        if isinstance(btype, str):
            btype = BookmarkType(btype)
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=btype,
            title=data.get("title", ""),
            url=data.get("url", ""),
            parent_id=data.get("parent_id"),
            position=data.get("position", 0),
            date_added=data.get("date_added", datetime.now().isoformat()),
            date_modified=data.get("date_modified", datetime.now().isoformat()),
            preferred_browser=data.get("preferred_browser"),
            source_browser=data.get("source_browser"),
            source_id=data.get("source_id"),
            children=children,
        )

    def get_folder_path(self, store: "BookmarkStore") -> str:
        """Get the full folder path for this bookmark (e.g., 'bookmark_bar/Dev')."""
        parts = []
        current = self
        while current.parent_id:
            parent = store.find_by_id(current.parent_id)
            if parent is None:
                break
            parts.append(parent.title)
            current = parent
        # Find root name
        for root_name, root_bm in store.roots.items():
            if root_bm.id == current.id or self._is_descendant_of(root_bm):
                parts.append(root_name)
                break
        parts.reverse()
        return "/".join(parts)

    def _is_descendant_of(self, ancestor: "Bookmark") -> bool:
        """Check if this bookmark is a descendant of the given ancestor."""
        for child in ancestor.children:
            if child.id == self.id:
                return True
            if child._is_descendant_of(ancestor):
                return True
        return False


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication comparison."""
    if not url:
        return ""
    parsed = urlparse(url)
    # Lowercase scheme and host
    scheme = parsed.scheme.lower()
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    # Reconstruct without fragment
    return f"{scheme}://{host}{path}" if host else url


@dataclass
class BookmarkStore:
    version: int = 1
    last_modified: str = field(default_factory=lambda: datetime.now().isoformat())
    roots: Dict[str, Bookmark] = field(default_factory=dict)

    def __post_init__(self):
        if not self.roots:
            now = datetime.now().isoformat()
            self.roots = {
                "bookmark_bar": Bookmark(
                    type=BookmarkType.FOLDER,
                    title="Bookmarks Bar",
                    date_added=now,
                    date_modified=now,
                ),
                "other": Bookmark(
                    type=BookmarkType.FOLDER,
                    title="Other Bookmarks",
                    date_added=now,
                    date_modified=now,
                ),
            }

    def to_dict(self) -> dict:
        """Convert the store to a JSON-serializable dictionary."""
        return {
            "version": self.version,
            "last_modified": self.last_modified,
            "roots": {k: v.to_dict() for k, v in self.roots.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BookmarkStore":
        """Create a BookmarkStore from a dictionary."""
        roots = {}
        for k, v in data.get("roots", {}).items():
            roots[k] = Bookmark.from_dict(v)
        return cls(
            version=data.get("version", 1),
            last_modified=data.get("last_modified", datetime.now().isoformat()),
            roots=roots,
        )

    def save(self, path: Optional[Path] = None) -> None:
        """Save the store to disk."""
        if path is None:
            path = get_bookmarks_file()
        self.last_modified = datetime.now().isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "BookmarkStore":
        """Load the store from disk. Returns a new empty store if file doesn't exist."""
        if path is None:
            path = get_bookmarks_file()
        if not path.exists():
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def backup(self) -> Path:
        """Create a timestamped backup of the current store file."""
        src = get_bookmarks_file()
        if not src.exists():
            self.save()
            src = get_bookmarks_file()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = get_backups_dir() / f"bookmarks_{timestamp}.json"
        shutil.copy2(src, dest)
        return dest

    def add(self, bookmark: Bookmark, parent_id: Optional[str] = None,
            root: str = "bookmark_bar") -> Bookmark:
        """Add a bookmark to the store.

        Args:
            bookmark: The bookmark to add.
            parent_id: ID of the parent folder. If None, adds to the root.
            root: Which root to add to if parent_id is None.

        Returns:
            The added bookmark.
        """
        if parent_id:
            parent = self.find_by_id(parent_id)
            if parent and parent.type == BookmarkType.FOLDER:
                bookmark.parent_id = parent_id
                bookmark.position = len(parent.children)
                parent.children.append(bookmark)
                parent.date_modified = datetime.now().isoformat()
                return bookmark
        # Add to root
        root_folder = self.roots.get(root)
        if root_folder:
            bookmark.parent_id = root_folder.id
            bookmark.position = len(root_folder.children)
            root_folder.children.append(bookmark)
            root_folder.date_modified = datetime.now().isoformat()
        return bookmark

    def remove(self, bookmark_id: str) -> Optional[Bookmark]:
        """Remove a bookmark by ID. Returns the removed bookmark or None."""
        for root in self.roots.values():
            result = self._remove_from(root, bookmark_id)
            if result:
                return result
        return None

    def _remove_from(self, parent: Bookmark, bookmark_id: str) -> Optional[Bookmark]:
        """Recursively search and remove a bookmark from a parent."""
        for i, child in enumerate(parent.children):
            if child.id == bookmark_id:
                removed = parent.children.pop(i)
                # Reindex positions
                for j, c in enumerate(parent.children):
                    c.position = j
                parent.date_modified = datetime.now().isoformat()
                return removed
            result = self._remove_from(child, bookmark_id)
            if result:
                return result
        return None

    def move(self, bookmark_id: str, new_parent_id: str, position: int = -1) -> bool:
        """Move a bookmark to a new parent at the given position.

        Returns True if successful.
        """
        bookmark = self.remove(bookmark_id)
        if not bookmark:
            return False

        new_parent = self.find_by_id(new_parent_id)
        if not new_parent or new_parent.type != BookmarkType.FOLDER:
            return False

        bookmark.parent_id = new_parent_id
        if position < 0 or position > len(new_parent.children):
            position = len(new_parent.children)
        new_parent.children.insert(position, bookmark)
        # Reindex
        for i, c in enumerate(new_parent.children):
            c.position = i
        new_parent.date_modified = datetime.now().isoformat()
        return True

    def find_by_id(self, bookmark_id: str) -> Optional[Bookmark]:
        """Find a bookmark by its ID."""
        for root in self.roots.values():
            if root.id == bookmark_id:
                return root
            result = self._find_in(root, bookmark_id)
            if result:
                return result
        return None

    def _find_in(self, parent: Bookmark, bookmark_id: str) -> Optional[Bookmark]:
        """Recursively search for a bookmark by ID."""
        for child in parent.children:
            if child.id == bookmark_id:
                return child
            result = self._find_in(child, bookmark_id)
            if result:
                return result
        return None

    def find_by_url(self, url: str) -> List[Bookmark]:
        """Find all bookmarks matching the given URL (normalized)."""
        target = normalize_url(url)
        results = []
        for root in self.roots.values():
            self._find_url_in(root, target, results)
        return results

    def _find_url_in(self, parent: Bookmark, target_url: str,
                     results: List[Bookmark]) -> None:
        """Recursively search for bookmarks by URL."""
        for child in parent.children:
            if child.type == BookmarkType.URL:
                if normalize_url(child.url) == target_url:
                    results.append(child)
            self._find_url_in(child, target_url, results)

    def find_by_source(self, source_browser: str, source_id: str) -> Optional[Bookmark]:
        """Find a bookmark by its source browser and source ID."""
        for root in self.roots.values():
            result = self._find_source_in(root, source_browser, source_id)
            if result:
                return result
        return None

    def _find_source_in(self, parent: Bookmark, source_browser: str,
                        source_id: str) -> Optional[Bookmark]:
        """Recursively search for a bookmark by source."""
        for child in parent.children:
            if child.source_browser == source_browser and child.source_id == source_id:
                return child
            result = self._find_source_in(child, source_browser, source_id)
            if result:
                return result
        return None

    def all_bookmarks(self) -> List[Bookmark]:
        """Return a flat list of all bookmarks (excluding root folders)."""
        results = []
        for root in self.roots.values():
            self._collect_all(root, results)
        return results

    def _collect_all(self, parent: Bookmark, results: List[Bookmark]) -> None:
        for child in parent.children:
            results.append(child)
            self._collect_all(child, results)

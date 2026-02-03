"""Edge bookmark reader/writer - delegates to Chrome with different paths/names."""

from pathlib import Path
from typing import Optional

from ..models.bookmark import BookmarkStore
from .chrome import read_chrome_bookmarks, write_chrome_bookmarks


def read_edge_bookmarks(bookmark_path: Optional[Path] = None) -> Optional[BookmarkStore]:
    """Read bookmarks from Edge's JSON file into a BookmarkStore."""
    return read_chrome_bookmarks(bookmark_path, source_browser="edge")


def write_edge_bookmarks(store: BookmarkStore,
                         bookmark_path: Optional[Path] = None) -> bool:
    """Write a BookmarkStore to Edge's JSON format."""
    return write_chrome_bookmarks(store, bookmark_path, source_browser="edge")

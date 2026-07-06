"""Convert between Bookmarker's ``BookmarkStore`` and the extension's browser-tree
JSON (chrome.bookmarks node shape).

Store roots map to Chromium's two editable root folders:
    ``bookmark_bar`` <-> "Bookmarks Bar" (browser node id "1")
    ``other``        <-> "Other Bookmarks" (browser node id "2")

Node dict shape (both directions)::

    {"store_id": str|None, "node_id": str|None, "title": str, "url": str,
     "is_folder": bool, "children": [ ...nodes... ]}
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..models.bookmark import Bookmark, BookmarkStore, BookmarkType

# Order matters: this is the order roots appear in the replace payload.
ROOT_KEYS = ("bookmark_bar", "other")


def _node_from_bookmark(bm: Bookmark) -> Dict[str, Any]:
    is_folder = bm.type == BookmarkType.FOLDER
    node: Dict[str, Any] = {
        "store_id": bm.id,
        "node_id": None,
        "title": bm.title,
        "url": "" if is_folder else bm.url,
        "is_folder": is_folder,
    }
    if is_folder:
        node["children"] = [
            _node_from_bookmark(c)
            for c in sorted(bm.children, key=lambda x: x.position)
        ]
    return node


def store_to_replace_tree(store: BookmarkStore) -> List[Dict[str, Any]]:
    """Full tree for the ``replace`` payload: one entry per root with its
    children as nodes. The extension wipes each root and recreates it."""
    result: List[Dict[str, Any]] = []
    for root_name in ROOT_KEYS:
        root = store.roots.get(root_name)
        children = (
            [_node_from_bookmark(c) for c in sorted(root.children, key=lambda x: x.position)]
            if root is not None
            else []
        )
        result.append({"root": root_name, "children": children})
    return result


def normalize_browser_tree(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Coerce an incoming browser-tree snapshot into the canonical shape, so
    reconciliation never trips over missing keys. Non-root or unknown-root
    entries are dropped."""
    out: List[Dict[str, Any]] = []
    by_root = {entry.get("root"): entry for entry in nodes if isinstance(entry, dict)}
    for root_name in ROOT_KEYS:
        entry = by_root.get(root_name, {})
        out.append({
            "root": root_name,
            "children": [_normalize_node(c) for c in entry.get("children", []) or []],
        })
    return out


def _normalize_node(node: Dict[str, Any]) -> Dict[str, Any]:
    is_folder = bool(node.get("is_folder")) or (
        "children" in node and not node.get("url")
    )
    out: Dict[str, Any] = {
        "store_id": node.get("store_id"),
        "node_id": node.get("node_id"),
        "title": str(node.get("title", "")),
        "url": "" if is_folder else str(node.get("url", "")),
        "is_folder": is_folder,
    }
    if is_folder:
        out["children"] = [_normalize_node(c) for c in node.get("children", []) or []]
    return out

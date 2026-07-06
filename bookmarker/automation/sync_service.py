"""Two-way reconciliation between the store and a running browser's bookmarks.

The unit of sync is a *key*, not a browser node id -- node ids are unstable
across the replace and not portable, so we match on structure instead:

    URL bookmark: (root, parent-folder-path, normalized url)
    folder:       (root, folder-path)

An ``idmap`` (the "known baseline") persists, per browser, the set of keys that
were synced on the last pass together with each URL's last-synced title. That
baseline drives two things Aaron asked for:

- **Mirror deletions, gated by the idmap.** An item present on one side and
  absent on the other is deleted from the first side ONLY if its key is in the
  baseline (so it existed and was removed). An item absent from the baseline is
  *new* and gets added to the other side -- never deleted. This prevents nuking
  bookmarks that were simply never synced.
- **3-way title merge.** When a URL exists on both sides with different titles,
  the baseline title tells us which side changed; that side wins. If both
  changed, the store (Bookmarker) is authoritative.

Replace/push is separate: it fully mirrors the store onto the browser and resets
the baseline to exactly the store's keys.

Pure Python (no Qt, no browser); the controller drives it.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..models.bookmark import Bookmark, BookmarkStore, BookmarkType, normalize_url
from ..operations.sync import _add_to_store_at_path
from ..utils.config import idmap_path
from . import messages, tree_codec

log = logging.getLogger(__name__)

_SEP = "\x00"


@dataclass
class _Item:
    root: str
    parent_path: Tuple[str, ...]  # ancestor folder titles (excl. root)
    title: str
    url: str
    is_folder: bool

    @property
    def path(self) -> Tuple[str, ...]:
        return self.parent_path + (self.title,) if self.is_folder else self.parent_path

    @property
    def key(self) -> str:
        if self.is_folder:
            return _SEP.join(("F", self.root, "/".join(self.path)))
        return _SEP.join(("U", self.root, "/".join(self.parent_path), normalize_url(self.url)))


@dataclass
class ReconcileResult:
    store_changed: bool = False
    ops: List[Dict[str, Any]] = field(default_factory=list)
    baseline: Dict[str, str] = field(default_factory=dict)  # key -> last-synced title


# --------------------------------------------------------------------- flatten


def _flatten_store(store: BookmarkStore) -> Dict[str, _Item]:
    out: Dict[str, _Item] = {}
    for root_name in tree_codec.ROOT_KEYS:
        root = store.roots.get(root_name)
        if root is None:
            continue
        _walk_store(root.children, root_name, (), out)
    return out


def _walk_store(children, root_name, parent_path, out):
    for bm in sorted(children, key=lambda x: x.position):
        if bm.type == BookmarkType.FOLDER:
            item = _Item(root_name, parent_path, bm.title, "", True)
            out[item.key] = item
            _walk_store(bm.children, root_name, parent_path + (bm.title,), out)
        else:
            item = _Item(root_name, parent_path, bm.title, bm.url, False)
            out[item.key] = item


def _flatten_browser(browser_roots: List[Dict[str, Any]]) -> Dict[str, _Item]:
    out: Dict[str, _Item] = {}
    for entry in tree_codec.normalize_browser_tree(browser_roots):
        _walk_browser(entry["children"], entry["root"], (), out)
    return out


def _walk_browser(nodes, root_name, parent_path, out):
    for node in nodes:
        if node.get("is_folder"):
            item = _Item(root_name, parent_path, node.get("title", ""), "", True)
            out[item.key] = item
            _walk_browser(node.get("children", []), root_name, parent_path + (item.title,), out)
        else:
            item = _Item(root_name, parent_path, node.get("title", ""), node.get("url", ""), False)
            out[item.key] = item


# --------------------------------------------------------------------- ops


def _create_op(item: _Item) -> Dict[str, Any]:
    return {
        "action": messages.ACTION_CREATE,
        "root": item.root,
        "path": list(item.parent_path),
        "title": item.title,
        "url": item.url,
        "is_folder": item.is_folder,
    }


def _remove_op(item: _Item) -> Dict[str, Any]:
    return {
        "action": messages.ACTION_REMOVE,
        "root": item.root,
        "path": list(item.parent_path),
        "title": item.title,
        "url": item.url,
        "is_folder": item.is_folder,
    }


def _update_op(item: _Item, title: str) -> Dict[str, Any]:
    return {
        "action": messages.ACTION_UPDATE,
        "root": item.root,
        "path": list(item.parent_path),
        "url": item.url,
        "title": title,
    }


# --------------------------------------------------------------------- store mutation


def _add_item_to_store(store: BookmarkStore, item: _Item) -> None:
    bm = Bookmark(
        type=BookmarkType.FOLDER if item.is_folder else BookmarkType.URL,
        title=item.title,
        url="" if item.is_folder else item.url,
        source_browser="browser-sync",
    )
    _add_to_store_at_path(store, bm, item.root, "/".join(item.parent_path))


def _remove_item_from_store(store: BookmarkStore, item: _Item) -> None:
    root = store.roots.get(item.root)
    if root is None:
        return
    parent = root
    for part in item.parent_path:
        nxt = next(
            (c for c in parent.children if c.type == BookmarkType.FOLDER and c.title == part),
            None,
        )
        if nxt is None:
            return
        parent = nxt
    for child in list(parent.children):
        if item.is_folder:
            if child.type == BookmarkType.FOLDER and child.title == item.title:
                store.remove(child.id)
                return
        else:
            if child.type == BookmarkType.URL and normalize_url(child.url) == normalize_url(item.url):
                store.remove(child.id)
                return


def _set_store_title(store: BookmarkStore, item: _Item, title: str) -> None:
    root = store.roots.get(item.root)
    if root is None:
        return
    parent = root
    for part in item.parent_path:
        nxt = next(
            (c for c in parent.children if c.type == BookmarkType.FOLDER and c.title == part),
            None,
        )
        if nxt is None:
            return
        parent = nxt
    for child in parent.children:
        if child.type == BookmarkType.URL and normalize_url(child.url) == normalize_url(item.url):
            child.title = title
            return


# --------------------------------------------------------------------- reconcile


def reconcile(
    store: BookmarkStore,
    browser_roots: List[Dict[str, Any]],
    baseline: Optional[Dict[str, str]] = None,
) -> ReconcileResult:
    """Compute the two-way delta between ``store`` and a browser-tree snapshot.

    Mutates ``store`` in place for store-side changes (caller saves). Returns the
    browser-side ops to send and the new baseline to persist.
    """
    baseline = baseline or {}
    store_flat = _flatten_store(store)
    browser_flat = _flatten_browser(browser_roots)

    result = ReconcileResult()
    new_baseline: Dict[str, str] = {}

    for key in set(store_flat) | set(browser_flat):
        s = store_flat.get(key)
        b = browser_flat.get(key)
        base = baseline.get(key)

        if s and b:
            if s.is_folder or s.title == b.title:
                new_baseline[key] = s.title
            else:
                # URL present both sides, titles differ -> 3-way merge.
                if base is not None and s.title == base and b.title != base:
                    _set_store_title(store, s, b.title)
                    result.store_changed = True
                    new_baseline[key] = b.title
                else:
                    # browser drifted, or both changed -> store authoritative.
                    result.ops.append(_update_op(s, s.title))
                    new_baseline[key] = s.title
        elif s and not b:
            if key in baseline:
                # was synced, gone from browser -> deleted in browser.
                _remove_item_from_store(store, s)
                result.store_changed = True
            else:
                # new in store -> create in browser.
                result.ops.append(_create_op(s))
                new_baseline[key] = s.title
        elif b and not s:
            if key in baseline:
                # deleted in store -> remove from browser.
                result.ops.append(_remove_op(b))
            else:
                # new in browser -> add to store.
                _add_item_to_store(store, b)
                result.store_changed = True
                new_baseline[key] = b.title

    result.ops = _order_ops(result.ops)
    result.baseline = new_baseline
    return result


def _order_ops(ops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Creates shallow->deep (folders before their contents); removes deep->
    shallow (contents before their folder). Updates last."""
    creates = [o for o in ops if o["action"] == messages.ACTION_CREATE]
    removes = [o for o in ops if o["action"] == messages.ACTION_REMOVE]
    updates = [o for o in ops if o["action"] == messages.ACTION_UPDATE]
    creates.sort(key=lambda o: (len(o["path"]), 0 if o["is_folder"] else 1))
    removes.sort(key=lambda o: (len(o["path"]) + (1 if not o["is_folder"] else 0)), reverse=True)
    return creates + updates + removes


# --------------------------------------------------------------------- replace


def build_replace_payload(store: BookmarkStore) -> List[Dict[str, Any]]:
    """Full tree for a replace/push: the extension wipes the roots and recreates
    them from this."""
    return tree_codec.store_to_replace_tree(store)


def baseline_from_store(store: BookmarkStore) -> Dict[str, str]:
    """The baseline that exactly matches ``store`` -- used to seed the idmap right
    after a replace, so the next reconcile treats everything as already synced."""
    return {key: item.title for key, item in _flatten_store(store).items()}


# --------------------------------------------------------------------- idmap I/O


def load_baseline(browser: str, path: Optional[Path] = None) -> Dict[str, str]:
    path = path or idmap_path(browser)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    keys = data.get("keys", {})
    return keys if isinstance(keys, dict) else {}


def save_baseline(browser: str, baseline: Dict[str, str], path: Optional[Path] = None) -> None:
    path = path or idmap_path(browser)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"keys": baseline}), encoding="utf-8")
    except OSError as exc:
        log.warning("could not write idmap %s: %s", path, exc)

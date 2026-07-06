"""Tests for store <-> browser-tree conversion."""

from bookmarker.models.bookmark import Bookmark, BookmarkStore, BookmarkType
from bookmarker.automation import tree_codec


def _store_with_content():
    store = BookmarkStore()
    bar = store.roots["bookmark_bar"]
    store.add(Bookmark(type=BookmarkType.URL, title="Ex", url="https://example.com"), parent_id=bar.id)
    folder = Bookmark(type=BookmarkType.FOLDER, title="Dev")
    store.add(folder, parent_id=bar.id)
    store.add(Bookmark(type=BookmarkType.URL, title="GH", url="https://github.com"), parent_id=folder.id)
    return store


def test_store_to_replace_tree_shape():
    tree = tree_codec.store_to_replace_tree(_store_with_content())
    assert [e["root"] for e in tree] == ["bookmark_bar", "other"]
    bar = tree[0]["children"]
    titles = [n["title"] for n in bar]
    assert "Ex" in titles and "Dev" in titles
    dev = next(n for n in bar if n["title"] == "Dev")
    assert dev["is_folder"] is True
    assert dev["url"] == ""
    assert [c["title"] for c in dev["children"]] == ["GH"]
    ex = next(n for n in bar if n["title"] == "Ex")
    assert ex["is_folder"] is False
    assert ex["url"] == "https://example.com"
    assert ex["store_id"]  # store GUID carried


def test_normalize_browser_tree_fills_missing_roots():
    # Only bookmark_bar supplied; normalizer must add an empty `other`.
    raw = [{"root": "bookmark_bar", "children": [
        {"node_id": "10", "title": "A", "url": "https://a.test", "is_folder": False},
    ]}]
    out = tree_codec.normalize_browser_tree(raw)
    assert [e["root"] for e in out] == ["bookmark_bar", "other"]
    assert out[1]["children"] == []
    node = out[0]["children"][0]
    assert node["node_id"] == "10" and node["url"] == "https://a.test"


def test_normalize_infers_folder_from_children():
    raw = [{"root": "other", "children": [
        {"node_id": "5", "title": "F", "children": [
            {"node_id": "6", "title": "B", "url": "https://b.test"},
        ]},
    ]}]
    out = tree_codec.normalize_browser_tree(raw)
    other = out[1]
    folder = other["children"][0]
    assert folder["is_folder"] is True
    assert folder["children"][0]["is_folder"] is False

"""Tests for the two-way reconciliation engine."""

from bookmarker.models.bookmark import Bookmark, BookmarkStore, BookmarkType
from bookmarker.automation import sync_service, messages


# --- builders ---------------------------------------------------------------


def _store(*bar_items):
    """bar_items: (title, url) tuples added to the Bookmarks Bar root."""
    store = BookmarkStore()
    bar = store.roots["bookmark_bar"]
    for title, url in bar_items:
        store.add(Bookmark(type=BookmarkType.URL, title=title, url=url), parent_id=bar.id)
    return store


def _url(title, url):
    return {"title": title, "url": url, "is_folder": False}


def _folder(title, children):
    return {"title": title, "url": "", "is_folder": True, "children": children}


def _snapshot(bar=None, other=None):
    return [
        {"root": "bookmark_bar", "children": bar or []},
        {"root": "other", "children": other or []},
    ]


def _titles_in_bar(store):
    return sorted(c.title for c in store.roots["bookmark_bar"].children)


# --- new items (no baseline) ------------------------------------------------


def test_store_only_creates_in_browser():
    store = _store(("Ex", "https://example.com"))
    result = sync_service.reconcile(store, _snapshot(), baseline={})
    assert result.store_changed is False
    assert len(result.ops) == 1
    assert result.ops[0]["action"] == messages.ACTION_CREATE
    assert result.ops[0]["url"] == "https://example.com"
    assert len(result.baseline) == 1


def test_browser_only_adds_to_store():
    store = _store()
    snap = _snapshot(bar=[_url("New", "https://new.test")])
    result = sync_service.reconcile(store, snap, baseline={})
    assert result.store_changed is True
    assert not result.ops
    assert "New" in _titles_in_bar(store)


def test_present_both_no_change():
    store = _store(("Ex", "https://example.com"))
    snap = _snapshot(bar=[_url("Ex", "https://example.com")])
    result = sync_service.reconcile(store, snap, baseline={})
    assert result.store_changed is False
    assert not result.ops
    assert len(result.baseline) == 1


# --- 3-way title merge ------------------------------------------------------


def test_title_conflict_browser_changed_updates_store():
    store = _store(("Old", "https://x.test"))
    snap = _snapshot(bar=[_url("NewFromBrowser", "https://x.test")])
    # baseline title == store's title ("Old") => browser is the one that changed.
    key = next(iter(sync_service.baseline_from_store(store)))
    result = sync_service.reconcile(store, snap, baseline={key: "Old"})
    assert result.store_changed is True
    assert _titles_in_bar(store) == ["NewFromBrowser"]
    assert not result.ops


def test_title_conflict_store_changed_updates_browser():
    store = _store(("NewFromStore", "https://x.test"))
    snap = _snapshot(bar=[_url("Old", "https://x.test")])
    # baseline title == browser's title ("Old") => store is the one that changed.
    key = next(iter(sync_service.baseline_from_store(store)))
    result = sync_service.reconcile(store, snap, baseline={key: "Old"})
    assert result.store_changed is False
    assert len(result.ops) == 1
    assert result.ops[0]["action"] == messages.ACTION_UPDATE
    assert result.ops[0]["title"] == "NewFromStore"


# --- mirror deletes, gated by baseline --------------------------------------


def test_deleted_in_browser_removed_from_store_when_known():
    store = _store(("Gone", "https://gone.test"))
    key = next(iter(sync_service.baseline_from_store(store)))
    # In baseline (was synced) but absent from the browser now => delete in store.
    result = sync_service.reconcile(store, _snapshot(), baseline={key: "Gone"})
    assert result.store_changed is True
    assert _titles_in_bar(store) == []
    assert not result.ops


def test_deleted_in_store_removed_from_browser_when_known():
    store = _store()  # store empty
    snap = _snapshot(bar=[_url("Gone", "https://gone.test")])
    # Reconstruct the key the browser item would have.
    tmp = _store(("Gone", "https://gone.test"))
    key = next(iter(sync_service.baseline_from_store(tmp)))
    result = sync_service.reconcile(store, snap, baseline={key: "Gone"})
    assert result.store_changed is False
    assert len(result.ops) == 1
    assert result.ops[0]["action"] == messages.ACTION_REMOVE


def test_never_synced_store_item_is_not_deleted():
    # Store has an item, browser empty, and it is NOT in the baseline.
    store = _store(("Keep", "https://keep.test"))
    result = sync_service.reconcile(store, _snapshot(), baseline={})
    assert _titles_in_bar(store) == ["Keep"]  # survived
    assert result.ops[0]["action"] == messages.ACTION_CREATE  # added to browser instead


# --- folders + ordering -----------------------------------------------------


def test_folder_create_ordered_before_its_url():
    store = BookmarkStore()
    bar = store.roots["bookmark_bar"]
    folder = Bookmark(type=BookmarkType.FOLDER, title="Dev")
    store.add(folder, parent_id=bar.id)
    store.add(Bookmark(type=BookmarkType.URL, title="GH", url="https://github.com"), parent_id=folder.id)

    result = sync_service.reconcile(store, _snapshot(), baseline={})
    actions = [(o["action"], o.get("is_folder"), o.get("title")) for o in result.ops]
    # folder create must come before the url create nested under it
    folder_idx = next(i for i, o in enumerate(result.ops) if o.get("is_folder"))
    url_idx = next(i for i, o in enumerate(result.ops) if o.get("url") == "https://github.com")
    assert folder_idx < url_idx


def test_browser_folder_and_url_added_to_store():
    store = _store()
    snap = _snapshot(bar=[_folder("Work", [_url("Site", "https://site.test")])])
    result = sync_service.reconcile(store, snap, baseline={})
    assert result.store_changed is True
    dev = next(c for c in store.roots["bookmark_bar"].children if c.title == "Work")
    assert dev.type == BookmarkType.FOLDER
    assert [c.title for c in dev.children] == ["Site"]


# --- replace helpers --------------------------------------------------------


def test_baseline_from_store_matches_replace():
    store = _store(("A", "https://a.test"), ("B", "https://b.test"))
    baseline = sync_service.baseline_from_store(store)
    assert len(baseline) == 2
    # Reconciling the store against a browser it was just replaced onto is a no-op.
    payload = sync_service.build_replace_payload(store)
    # Emulate the browser now holding exactly the replace payload.
    result = sync_service.reconcile(store, payload, baseline=baseline)
    assert not result.ops
    assert result.store_changed is False


def test_idmap_persistence(isolate_config):
    baseline = {"k1": "t1", "k2": "t2"}
    sync_service.save_baseline("chrome", baseline)
    assert sync_service.load_baseline("chrome") == baseline
    assert sync_service.load_baseline("edge") == {}

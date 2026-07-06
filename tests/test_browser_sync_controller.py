"""Tests for the browser-sync controller's sync_finished signal (drives the
extension-sync progress popup)."""

import sys

import pytest

from bookmarker.models.bookmark import Bookmark, BookmarkStore, BookmarkType


@pytest.fixture
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


def _controller(store):
    from bookmarker.automation.controller import BrowserSyncController
    return BrowserSyncController(store)


def test_on_tree_emits_sync_finished(qapp, isolate_config):
    store = BookmarkStore()
    ctrl = _controller(store)
    summaries = []
    ctrl.sync_finished.connect(summaries.append)
    # Empty browser tree against empty store -> reconcile no-op, but the pass
    # still completes and reports.
    ctrl._on_tree({"type": "tree", "browser": "chrome", "nodes": []})
    assert len(summaries) == 1
    assert "Synced" in summaries[0]


def test_on_tree_reports_browser_changes(qapp, isolate_config):
    # Store has one bookmark the (empty) browser lacks -> one create op queued;
    # summary should mention a browser change.
    store = BookmarkStore()
    bar = store.roots["bookmark_bar"]
    store.add(Bookmark(title="Ex", url="https://example.com", type=BookmarkType.URL),
              parent_id=bar.id)
    ctrl = _controller(store)
    summaries = []
    ctrl.sync_finished.connect(summaries.append)
    ctrl._on_tree({"type": "tree", "browser": "chrome", "nodes": []})
    assert summaries and "1 browser change" in summaries[0]

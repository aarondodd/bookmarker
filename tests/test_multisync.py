"""Tests for the cancellable multi-browser two-way sync worker."""

import sys

import pytest

from bookmarker.models.bookmark import BookmarkStore
from bookmarker.operations import sync as syncmod
from bookmarker.operations.sync import MultiSyncWorker


@pytest.fixture
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


def _capture(worker):
    out = []
    worker.finished_sync.connect(lambda s, b, e: out.append((s, b, e)))
    return out


def test_runs_all_browsers(qapp, monkeypatch):
    executed = []
    monkeypatch.setattr(syncmod, "plan_sync", lambda store, name, path=None: (["a1"], None, None))

    def fake_exec(store, name, actions, path=None):
        executed.append(name)
        return (1, 2, None)

    monkeypatch.setattr(syncmod, "execute_sync", fake_exec)
    worker = MultiSyncWorker(["chrome", "edge"], BookmarkStore())
    out = _capture(worker)
    worker.run()  # synchronous
    assert executed == ["chrome", "edge"]
    assert out[0] == (2, 4, "")  # store/browser totals summed, no errors


def test_cancel_before_run_does_nothing(qapp, monkeypatch):
    executed = []
    monkeypatch.setattr(syncmod, "plan_sync", lambda *a, **k: (["a1"], None, None))
    monkeypatch.setattr(
        syncmod, "execute_sync",
        lambda store, name, actions, path=None: (executed.append(name) or (1, 1, None)),
    )
    worker = MultiSyncWorker(["chrome", "edge"], BookmarkStore())
    worker.cancel()
    out = _capture(worker)
    worker.run()
    assert executed == []
    assert "Cancelled" in out[0][2]


def test_no_actions_skips_execute(qapp, monkeypatch):
    executed = []
    monkeypatch.setattr(syncmod, "plan_sync", lambda store, name, path=None: ([], None, None))
    monkeypatch.setattr(
        syncmod, "execute_sync",
        lambda store, name, actions, path=None: (executed.append(name) or (0, 0, None)),
    )
    worker = MultiSyncWorker(["chrome"], BookmarkStore())
    out = _capture(worker)
    worker.run()
    assert executed == []          # nothing to do -> execute not called
    assert out[0] == (0, 0, "")


def test_errors_collected(qapp, monkeypatch):
    monkeypatch.setattr(syncmod, "plan_sync", lambda store, name, path=None: ([], None, "boom"))
    monkeypatch.setattr(syncmod, "execute_sync", lambda *a, **k: (0, 0, None))
    worker = MultiSyncWorker(["chrome"], BookmarkStore())
    out = _capture(worker)
    worker.run()
    assert "boom" in out[0][2]

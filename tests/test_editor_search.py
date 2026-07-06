"""Tests for the editor's fuzzy search box."""

import os
import sys

import pytest

from bookmarker.models.bookmark import Bookmark, BookmarkType, BookmarkStore

pytestmark = pytest.mark.skipif(
    not bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")),
    reason="No display available",
)


@pytest.fixture
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def editor(qapp, isolate_config):
    from bookmarker.ui.editor import BookmarkEditorWindow
    store = BookmarkStore()
    bar = store.roots["bookmark_bar"]
    store.add(Bookmark(title="Example", url="https://example.com"), parent_id=bar.id)
    folder = Bookmark(title="Dev", type=BookmarkType.FOLDER)
    store.add(folder, parent_id=bar.id)
    store.add(Bookmark(title="GitHub", url="https://github.com"), parent_id=folder.id)
    store.add(Bookmark(title="GitLab", url="https://gitlab.com"), parent_id=folder.id)
    store.save()
    return BookmarkEditorWindow(store)


def _result_titles(editor):
    out = []
    for i in range(editor._results_list.count()):
        out.append(editor._results_list.item(i).text().split("\n")[0])
    return out


def test_typing_switches_to_results(editor):
    assert editor._left_stack.currentIndex() == 0  # tree by default
    editor._search_edit.setText("git")
    assert editor._left_stack.currentIndex() == 1  # results view
    titles = _result_titles(editor)
    assert any("GitHub" in t for t in titles)
    assert any("GitLab" in t for t in titles)


def test_clearing_restores_tree(editor):
    editor._search_edit.setText("git")
    assert editor._left_stack.currentIndex() == 1
    editor._search_edit.setText("")
    assert editor._left_stack.currentIndex() == 0


def test_top_result_previews_in_edit_panel(editor):
    from PyQt6.QtCore import Qt
    editor._search_edit.setText("GitHub")
    # first row auto-selected -> edit panel + tree selection follow
    assert editor._current_item is not None
    assert editor._current_item.title == "GitHub"
    assert editor._title_edit.text() == "GitHub"
    tree_item = editor._tree.currentItem()
    assert tree_item is not None
    # Tree selection mirrors the chosen result (Delete/Move/Save target it).
    assert tree_item.data(0, Qt.ItemDataRole.UserRole) == editor._current_item.id


def test_fuzzy_subsequence_matches(editor):
    # 'gh' is a subsequence of 'GitHub' but not a substring.
    editor._search_edit.setText("gh")
    assert any("GitHub" in t for t in _result_titles(editor))


def test_no_match_shows_empty_results(editor):
    editor._search_edit.setText("zzzzz")
    assert editor._results_list.count() == 0
    assert editor._left_stack.currentIndex() == 1


def test_folder_is_searchable(editor):
    editor._search_edit.setText("Dev")
    titles = _result_titles(editor)
    assert any(t.startswith("[F] Dev") for t in titles)

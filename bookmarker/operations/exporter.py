"""Export/push orchestrator - pushes bookmarks from the store to browsers."""

from typing import List

from PyQt6.QtCore import QThread, pyqtSignal

from ..models.bookmark import BookmarkStore
from .chrome import write_chrome_bookmarks
from .edge import write_edge_bookmarks
from .firefox import write_firefox_bookmarks
from .browser_detect import is_browser_running, CHROME_PROCESS_NAMES, EDGE_PROCESS_NAMES, FIREFOX_PROCESS_NAMES


def push_to_browser(browser_name: str, store: BookmarkStore,
                    bookmark_path=None) -> tuple:
    """Push the entire store to a browser, replacing its bookmarks.

    The browser must be closed.

    Args:
        browser_name: "chrome", "edge", or "firefox"
        store: The BookmarkStore to push
        bookmark_path: Optional explicit path to bookmark file

    Returns:
        Tuple of (success: bool, error_message_or_none)
    """
    # Check if browser is running
    process_map = {
        "chrome": CHROME_PROCESS_NAMES,
        "edge": EDGE_PROCESS_NAMES,
        "firefox": FIREFOX_PROCESS_NAMES,
    }
    procs = process_map.get(browser_name)
    if procs and is_browser_running(procs):
        return False, f"{browser_name} is running. Please close it first."

    # Backup store before push
    store.backup()

    if browser_name == "chrome":
        success = write_chrome_bookmarks(store, bookmark_path)
    elif browser_name == "edge":
        success = write_edge_bookmarks(store, bookmark_path)
    elif browser_name == "firefox":
        success = write_firefox_bookmarks(store, bookmark_path)
    else:
        return False, f"Unknown browser: {browser_name}"

    if success:
        return True, None
    return False, f"Failed to write bookmarks to {browser_name}"


class ExportWorker(QThread):
    """Worker thread for pushing bookmarks to browsers."""

    progress = pyqtSignal(str)  # Status message
    finished_export = pyqtSignal(bool, str)  # success, error

    def __init__(self, browsers: List[str], store: BookmarkStore, parent=None):
        super().__init__(parent)
        self.browsers = browsers
        self.store = store

    def run(self):
        errors = []
        all_success = True

        for browser in self.browsers:
            self.progress.emit(f"Pushing to {browser}...")
            success, error = push_to_browser(browser, self.store)
            if not success:
                all_success = False
                if error:
                    errors.append(error)

        error_msg = "; ".join(errors) if errors else ""
        self.finished_export.emit(all_success, error_msg)

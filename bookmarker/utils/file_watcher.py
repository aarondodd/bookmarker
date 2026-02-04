"""File watcher for detecting external changes to bookmarks.json."""

from PyQt6.QtCore import QObject, QFileSystemWatcher, QTimer, pyqtSignal

from .config import get_bookmarks_file


class BookmarkFileWatcher(QObject):
    """Watches the bookmarks.json file for external modifications.

    Uses QFileSystemWatcher with debouncing to avoid rapid-fire signals.
    Provides pause/resume to avoid false triggers during self-save operations.
    """

    file_changed = pyqtSignal()

    # Debounce delay in milliseconds
    DEBOUNCE_MS = 100
    # Resume delay after pause (to allow file system to settle)
    RESUME_DELAY_MS = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self._watcher = QFileSystemWatcher(self)
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._emit_change)

        self._resume_timer = QTimer(self)
        self._resume_timer.setSingleShot(True)
        self._resume_timer.timeout.connect(self._do_resume)

        self._paused = False
        self._watching = False
        self._pending_change = False

        self._watcher.fileChanged.connect(self._on_file_changed)

    def start(self):
        """Start watching the bookmarks file."""
        if self._watching:
            return

        path = get_bookmarks_file()
        if path.exists():
            self._watcher.addPath(str(path))
            self._watching = True

    def stop(self):
        """Stop watching the bookmarks file."""
        if not self._watching:
            return

        path = get_bookmarks_file()
        self._watcher.removePath(str(path))
        self._watching = False
        self._debounce_timer.stop()
        self._resume_timer.stop()

    def pause(self):
        """Pause watching before a self-save operation.

        Call this before saving the store to avoid false change triggers.
        """
        self._paused = True
        self._debounce_timer.stop()
        self._resume_timer.stop()

    def resume(self):
        """Resume watching after a self-save operation.

        Waits a short delay before actually resuming to let the
        file system settle after the save.
        """
        # Schedule the actual resume with a delay
        self._resume_timer.start(self.RESUME_DELAY_MS)

    def _do_resume(self):
        """Actually resume watching after the delay."""
        self._paused = False
        self._pending_change = False

        # Re-add the path - QFileSystemWatcher removes paths after notification
        # on some platforms, so we ensure it's being watched
        path = get_bookmarks_file()
        if path.exists() and self._watching:
            # Remove first to avoid duplicate watching
            self._watcher.removePath(str(path))
            self._watcher.addPath(str(path))

    def _on_file_changed(self, path: str):
        """Handle file change notification from QFileSystemWatcher."""
        # Re-add the path - QFileSystemWatcher removes it after notification
        # on some platforms (notably Linux with inotify when file is replaced)
        bookmarks_path = get_bookmarks_file()
        if bookmarks_path.exists():
            self._watcher.addPath(str(bookmarks_path))

        if self._paused:
            self._pending_change = True
            return

        # Debounce: restart the timer on each change
        self._debounce_timer.start(self.DEBOUNCE_MS)

    def _emit_change(self):
        """Emit the file_changed signal after debounce period."""
        if not self._paused:
            self.file_changed.emit()

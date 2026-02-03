"""Main application - system tray + window management."""

import sys
from typing import Optional, List

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QMainWindow, QSystemTrayIcon, QMenu, QMessageBox, QApplication,
)

from .models.bookmark import BookmarkStore
from .operations.importer import ImportWorker
from .operations.exporter import ExportWorker
from .operations.sync import SyncWorker, SyncAction, plan_sync, execute_sync
from .operations.browser_detect import detect_browsers
from .utils.config import (
    get_ui_config, set_ui_config, get_sync_config, create_default_config,
)
from .utils.icon import generate_tray_icon
from .utils.theme import ThemeManager
from .utils.updater import check_for_updates, upgrade
from .ui.editor import BookmarkEditorWindow
from .ui.browser_dialog import BrowserSelectionDialog
from .ui.debug_dialog import DebugConfirmDialog
from .ui.sync_dialog import SyncProgressDialog
from .ui.settings_dialog import SettingsDialog
from .ui.quick_launch import QuickLaunchWindow
from .utils.launcher import launch_bookmark
from .models.bookmark import BookmarkType


class UpgradeWorker(ImportWorker.__bases__[0]):
    """Worker thread for upgrade operations."""
    # Inherits from QThread

    from PyQt6.QtCore import pyqtSignal
    progress = pyqtSignal(str, str)
    finished_upgrade = pyqtSignal(bool, str)

    def run(self):
        def progress_cb(stage, msg):
            self.progress.emit(stage, msg)

        success, message = upgrade(progress_callback=progress_cb)
        self.finished_upgrade.emit(success, message)


class BookmarkerApp(QMainWindow):
    """Main application window with system tray integration."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bookmarker")

        self.store = BookmarkStore.load()
        self._editor: Optional[BookmarkEditorWindow] = None
        self._sync_dialog: Optional[SyncProgressDialog] = None
        self._quick_launch: Optional[QuickLaunchWindow] = None

        # Apply theme
        ui_config = get_ui_config()
        dark = ui_config.get("dark_mode", False)
        ThemeManager.apply(dark)

        # System tray
        self._setup_tray()

        # Auto-check for updates after 3 seconds
        QTimer.singleShot(3000, self._auto_check_for_updates)

    def _setup_tray(self):
        """Set up the system tray icon and context menu."""
        self._tray = QSystemTrayIcon(self)
        self._update_tray_icon("normal")
        self._tray.setToolTip("Bookmarker")
        self._tray.activated.connect(self._on_tray_activated)

        menu = QMenu()

        # Launch submenu - bookmark hierarchy
        self._launch_menu = menu.addMenu("Launch")
        self._launch_menu.aboutToShow.connect(self._populate_launch_menu)

        menu.addSeparator()

        open_editor_action = menu.addAction("Open Editor")
        open_editor_action.triggered.connect(self._open_editor)

        add_from_clipboard_action = menu.addAction("Add Bookmark from Clipboard")
        add_from_clipboard_action.triggered.connect(self._add_bookmark_from_clipboard)

        menu.addSeparator()

        import_action = menu.addAction("Import Bookmarks")
        import_action.triggered.connect(self._import_bookmarks)

        push_action = menu.addAction("Push Bookmarks")
        push_action.triggered.connect(self._push_bookmarks)

        sync_action = menu.addAction("Sync")
        sync_action.triggered.connect(self._sync_bookmarks)

        menu.addSeparator()

        settings_action = menu.addAction("Settings")
        settings_action.triggered.connect(self._open_settings)

        theme_action = menu.addAction("Toggle Dark/Light Mode")
        theme_action.triggered.connect(self._toggle_theme)

        menu.addSeparator()

        check_updates_action = menu.addAction("Check for Updates")
        check_updates_action.triggered.connect(self._check_for_updates)

        upgrade_action = menu.addAction("Upgrade")
        upgrade_action.triggered.connect(self._do_upgrade)

        menu.addSeparator()

        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(self._quit)

        self._tray.setContextMenu(menu)
        self._tray.show()

    def _populate_launch_menu(self):
        """Populate the Launch submenu with bookmark hierarchy."""
        self._launch_menu.clear()

        # Add bookmarks from all roots
        for root_name, root_bm in self.store.roots.items():
            for child in sorted(root_bm.children, key=lambda x: x.position):
                self._add_bookmark_to_menu(self._launch_menu, child)

    def _add_bookmark_to_menu(self, menu: QMenu, bookmark):
        """Add a bookmark or folder to a menu."""
        if bookmark.type == BookmarkType.FOLDER:
            # Create submenu for folder
            submenu = menu.addMenu(f"\U0001F4C1 {bookmark.title}")
            for child in sorted(bookmark.children, key=lambda x: x.position):
                self._add_bookmark_to_menu(submenu, child)
        else:
            # Add action for bookmark
            action = menu.addAction(f"\U0001F517 {bookmark.title}")
            action.setToolTip(bookmark.url)
            # Use lambda with default argument to capture bookmark
            action.triggered.connect(
                lambda checked, bm=bookmark: self._launch_bookmark_from_menu(bm)
            )

    def _launch_bookmark_from_menu(self, bookmark):
        """Launch a bookmark from the context menu."""
        launch_bookmark(bookmark)

    def _update_tray_icon(self, state: str = "normal"):
        """Update the tray icon based on state."""
        icon = generate_tray_icon(state, ThemeManager.is_dark_mode())
        self._tray.setIcon(icon)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Single click - show quick launch
            self._open_quick_launch()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._open_editor()

    def _open_quick_launch(self):
        """Open the quick launch window."""
        if self._quick_launch is None or not self._quick_launch.isVisible():
            self._quick_launch = QuickLaunchWindow(self.store)
            self._quick_launch.closed.connect(self._on_quick_launch_closed)
        else:
            # If already visible, just focus it
            self._quick_launch.raise_()
            self._quick_launch.activateWindow()
            return
        self._quick_launch.show()
        self._quick_launch.raise_()
        self._quick_launch.activateWindow()

    def _on_quick_launch_closed(self):
        """Handle quick launch window closing."""
        self._quick_launch = None

    def _open_editor(self):
        """Open the bookmark editor window."""
        if self._editor is None or not self._editor.isVisible():
            self._editor = BookmarkEditorWindow(self.store)
            self._editor.store_changed.connect(self._on_store_changed)
        self._editor.show()
        self._editor.raise_()
        self._editor.activateWindow()

    def _add_bookmark_from_clipboard(self):
        """Add a new bookmark using the clipboard contents as URL."""
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()

        if not text:
            QMessageBox.warning(
                None, "Empty Clipboard",
                "The clipboard is empty. Copy a URL first.")
            return

        # Basic URL validation - check if it looks like a URL
        if not (text.startswith("http://") or text.startswith("https://") or
                text.startswith("file://") or "." in text):
            QMessageBox.warning(
                None, "Invalid URL",
                f"The clipboard contents don't appear to be a valid URL:\n{text[:100]}")
            return

        # Add http:// prefix if missing
        if not text.startswith(("http://", "https://", "file://")):
            text = "https://" + text

        # Open editor with the URL pre-filled
        if self._editor is None or not self._editor.isVisible():
            self._editor = BookmarkEditorWindow(self.store)
            self._editor.store_changed.connect(self._on_store_changed)

        self._editor.show()
        self._editor.raise_()
        self._editor.activateWindow()
        self._editor.add_bookmark_with_url(text)

    def _on_store_changed(self):
        """Handle store changes from the editor."""
        self.store.save()

    def _import_bookmarks(self):
        """Show browser selection dialog and import bookmarks."""
        dialog = BrowserSelectionDialog("Import Bookmarks", "import", self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        browsers = dialog.selected_browsers()
        if not browsers:
            return

        progress = SyncProgressDialog("Importing Bookmarks", self)
        progress.show()

        self._update_tray_icon("syncing")

        self._import_worker = ImportWorker(browsers, self.store)
        self._import_worker.progress.connect(progress.set_status)

        def on_finished(added, skipped, error):
            self._update_tray_icon("normal")
            if error:
                progress.finish(f"Import completed with errors: {error}\n"
                                f"Added: {added}, Skipped: {skipped}")
            else:
                progress.finish(f"Import complete. Added: {added}, Skipped: {skipped}")
            self.store.save()
            if self._editor:
                self._editor.refresh()

        self._import_worker.finished_import.connect(on_finished)
        self._import_worker.start()

    def _push_bookmarks(self):
        """Show browser selection dialog and push bookmarks."""
        dialog = BrowserSelectionDialog("Push Bookmarks", "push", self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        browsers = dialog.selected_browsers()
        if not browsers:
            return

        # Warn about running browsers
        running = []
        for browser in detect_browsers():
            if browser.name in browsers and browser.running:
                running.append(browser.display_name)
        if running:
            QMessageBox.warning(
                self, "Browsers Running",
                f"Please close these browsers first: {', '.join(running)}")
            return

        progress = SyncProgressDialog("Pushing Bookmarks", self)
        progress.show()

        self._update_tray_icon("syncing")

        self._export_worker = ExportWorker(browsers, self.store)
        self._export_worker.progress.connect(progress.set_status)

        def on_finished(success, error):
            self._update_tray_icon("normal")
            if error:
                progress.finish(f"Push completed with errors: {error}")
            else:
                progress.finish("Push complete. All browsers updated.")

        self._export_worker.finished_export.connect(on_finished)
        self._export_worker.start()

    def _sync_bookmarks(self):
        """Run bidirectional sync with all installed browsers."""
        browsers = [b.name for b in detect_browsers() if b.installed]
        if not browsers:
            QMessageBox.information(self, "No Browsers", "No browsers detected.")
            return

        debug_mode = get_sync_config().get("debug_mode", False)

        progress = SyncProgressDialog("Syncing Bookmarks", self)
        progress.show()
        self._update_tray_icon("syncing")

        total_store = 0
        total_browser = 0
        errors = []

        for browser_name in browsers:
            progress.set_status(f"Planning sync with {browser_name}...")
            actions, _, error = plan_sync(self.store, browser_name)
            if error:
                errors.append(error)
                continue

            if not actions:
                progress.set_status(f"{browser_name}: Already in sync.")
                continue

            # Debug mode: confirm each action
            if debug_mode:
                approved = []
                apply_all = False
                for i, action in enumerate(actions):
                    if apply_all:
                        approved.append(action)
                        continue
                    dlg = DebugConfirmDialog(action, i + 1, len(actions), self)
                    dlg.exec()
                    if dlg.result_action == DebugConfirmDialog.APPLY:
                        approved.append(action)
                    elif dlg.result_action == DebugConfirmDialog.APPLY_ALL:
                        approved.append(action)
                        apply_all = True
                actions = approved

            progress.set_status(f"Applying {len(actions)} changes for {browser_name}...")
            sc, bc, err = execute_sync(self.store, browser_name, actions)
            total_store += sc
            total_browser += bc
            if err:
                errors.append(err)

        self._update_tray_icon("normal")
        error_msg = f"\nErrors: {'; '.join(errors)}" if errors else ""
        progress.finish(
            f"Sync complete. Store changes: {total_store}, "
            f"Browser changes: {total_browser}{error_msg}")

        if self._editor:
            self._editor.refresh()

    def _open_settings(self):
        """Open the settings dialog."""
        dialog = SettingsDialog(self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            ThemeManager.apply(dialog.is_dark_mode())
            self._update_tray_icon()

    def _toggle_theme(self):
        """Toggle between dark and light mode."""
        dark = not ThemeManager.is_dark_mode()
        ThemeManager.apply(dark)
        set_ui_config({"dark_mode": dark})
        self._update_tray_icon()

    def _auto_check_for_updates(self):
        """Check for updates on startup (silent)."""
        result = check_for_updates()
        if result:
            local_ver, remote_ver = result
            self._tray.showMessage(
                "Update Available",
                f"Bookmarker {remote_ver} is available (current: {local_ver}). "
                f"Right-click tray icon to upgrade.",
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )

    def _check_for_updates(self):
        """Manual check for updates."""
        result = check_for_updates()
        if result:
            local_ver, remote_ver = result
            QMessageBox.information(
                self, "Update Available",
                f"Version {remote_ver} is available (current: {local_ver}).\n"
                f"Use the Upgrade option to install it.")
        else:
            from .version import __version__
            QMessageBox.information(
                self, "Up to Date",
                f"You are running the latest version ({__version__}).")

    def _do_upgrade(self):
        """Perform the upgrade."""
        progress = SyncProgressDialog("Upgrading Bookmarker", self)
        progress.show()

        self._upgrade_worker = UpgradeWorker()
        self._upgrade_worker.progress.connect(
            lambda stage, msg: progress.set_status(f"[{stage}] {msg}"))

        def on_finished(success, message):
            if success:
                progress.finish(f"Upgrade complete: {message}")
            else:
                progress.finish(f"Upgrade failed: {message}")

        self._upgrade_worker.finished_upgrade.connect(on_finished)
        self._upgrade_worker.start()

    def _quit(self):
        """Save and quit."""
        self.store.save()
        self._tray.hide()
        QApplication.quit()

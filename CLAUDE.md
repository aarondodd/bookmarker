# Bookmarker

Cross-browser bookmark manager with a unified internal store.

## Project Structure

- `main.py` - Entry point
- `bookmarker/` - Main package
  - `app.py` - BookmarkerApp (QMainWindow + system tray)
  - `version.py` - Version string
  - `models/bookmark.py` - Bookmark dataclass + BookmarkStore
  - `operations/` - Browser I/O (chrome, edge, firefox, sync, importer, exporter)
  - `utils/` - Config, icon, theme, updater, launcher, fuzzy (pure-Python fuzzy matcher)
  - `ui/` - Editor, dialogs, quick_launch
- `tests/` - pytest test suite

## Commands

```bash
# Install dependencies
.venv/bin/pip install -r requirements.txt

# Run all tests
.venv/bin/python -m pytest tests/ -v

# Run a single test file
.venv/bin/python -m pytest tests/test_models.py -v

# Run the app
.venv/bin/python main.py

# Build the onedir bundle (also installs to ~/.local/share + ~/bin)
./build.sh
# Build only, no local install (what CI runs):
BOOKMARKER_NO_INSTALL=1 ./build.sh
```

Note: hotkey/UI tests import `pynput`, which needs an X display -- run the suite
with `DISPLAY=:10` set, otherwise `tests/test_hotkey.py` false-fails headless.

## Build & Release

Packaging follows the meeting-notetaker pattern: PyInstaller **--onedir** (config
lives entirely in `bookmarker.spec`, not inline build flags), wrapped per platform
and attached to GitHub Releases by CI.

- `bookmarker.spec` -- onedir (`EXE(exclude_binaries=True)` + `COLLECT`). Collects
  PyQt6, plus `pynput` and (Linux-only, guarded) `Xlib` so the global-hotkey
  backend actually ships in frozen builds. Bundles `utils/bookmark.png`.
- `build.sh` / `build.ps1` -- run `pyinstaller --noconfirm --clean bookmarker.spec`.
  Local install puts the whole onedir dir under `~/.local/share/bookmarker/`
  (or `%USERPROFILE%\bin\bookmarker\`) and symlinks the launcher; skip with
  `BOOKMARKER_NO_INSTALL=1`.
- `installer.iss` -- Inno Setup script (Windows). Stable AppId, per-user default,
  `CloseApplications`/`RestartApplications` (needed for silent self-upgrade),
  recurses `dist\bookmarker\*` into the install dir. Output:
  `bookmarker-setup-X.Y.Z.exe`.
- `.github/workflows/release.yml` -- on tag `v*` (or manual dispatch): a
  **windows-latest** job builds the Inno installer, an **ubuntu-22.04** job
  (older glibc for compatibility) tars the onedir bundle as
  `bookmarker-linux-x86_64-X.Y.Z.tar.gz` (with an `install.sh` inside). Both
  attach to the tag's release.
- **Release cadence**: bump `bookmarker/version.py`, commit, `git tag vX.Y.Z &&
  git push origin vX.Y.Z`. Exercise via `workflow_dispatch` first to smoke the
  build without cutting a release.
- `upgrade.ps1` (Windows, ported from meeting-notetaker): reads the installed
  version from the Inno uninstall registry (AppId `{1F6B8A6C-...}_is1`, HKCU/HKLM),
  compares to the latest release, downloads + runs the setup.exe silently. For
  users who prefer a one-liner over the in-app updater.

## Self-update (`utils/updater.py`)

Platform-aware, asset-based -- no build toolchain needed on the user's machine.
`install_kind()` picks the path:

- **windows-installer** (frozen, Windows): download `bookmarker-setup-X.Y.Z.exe`,
  run it `/SILENT /SUPPRESSMSGBOXES /NORESTART` detached, exit. Inno Setup's
  Restart Manager closes+relaunches the app and upgrades in place.
- **linux-tarball** (frozen, Linux): download the tarball, extract beside the
  onedir bundle (`Path(sys.executable).parent`), swap `bundle -> bundle.old` /
  `new -> bundle`, then `os.execv` the fresh launcher. `cleanup_stale_bundle()`
  removes `bundle.old` on next start; `prune_updates_cache()` bounds the download
  cache. Both are called from `app.py.__init__`.
- **source** (not frozen): advises `git pull` + `build.sh`/`build.ps1` -- does not
  auto-rebuild.

`check_for_updates()` (weekly interval) and `upgrade(progress_callback=...)` are
unchanged in signature, so `app.py`'s `UpgradeWorker`/menu wiring is untouched.

## Browser Sync (live extension) -- implemented (Chromium)

Keeps a *running* Chrome/Edge browser in sync with the store via an MV3 extension
+ Native Messaging (the file-based import/push/sync still requires the browser
closed). Design rationale in `docs/browser-extension-feasibility.md`; user/dev
guide in `docs/browser-sync.md`.

- **`bookmarker/automation/`** (new package):
  - `protocol.py` -- length-prefixed JSON framing (both hops).
  - `bridge.py` -- app-side one-peer loopback TCP server; writes
    `~/.bookmarker/automation/bridge.json` (port + per-launch token); token
    handshake. Pure Python (no Qt).
  - `native_host.py` -- the `--native-host` stdio<->TCP relay Chrome spawns.
  - `messages.py` -- app<->ext schema (ping/replace/apply_ops/request_tree ->
    pong/tree/error) + op/event actions.
  - `tree_codec.py` -- BookmarkStore <-> browser-tree JSON; roots `bookmark_bar`
    /`other` map to Chromium root ids "1"/"2".
  - `sync_service.py` -- two-way reconcile keyed by (root, path, normalized URL);
    baseline at `idmap-<browser>.json`; **mirror deletes gated by the baseline**;
    3-way title merge (store authoritative on double-change).
  - `installer.py` -- extract extension to `automation/extension/`, write native-
    host manifest per Chromium browser (Linux/mac dirs; Windows HKCU). Pinned
    `EXTENSION_ID` derived from the manifest `key` (validated on extract).
  - `controller.py` -- `BrowserSyncController(QObject)`: owns the Bridge, marshals
    to the Qt main thread, drives `replace()`/`sync_now()` + the auto-sync QTimer.
- **`bookmarker/resources/extension/`** -- MV3 extension (manifest with fixed
  `key`, `background.js` service worker using `chrome.bookmarks`, popup, icons).
  Bundled into frozen builds via `bookmarker.spec` datas; extracted by installer.
- **Wiring**: `main.py` dispatches `--native-host` before QApplication; `app.py`
  starts the controller. The tray has a **Sync** submenu: "Sync Browser via
  Extension" (live; opens a `SyncProgressDialog` that follows `controller.status`
  + `sync_finished` with a 20s timeout) + Direct "browser closed" actions (Import
  from Browser Direct / Push to Browser Direct / Two-Way Sync Direct). Two-Way
  Sync Direct prompts for the target browser (`BrowserSelectionDialog`
  operation="sync"), aborts if it's open, and runs in a cancellable
  `MultiSyncWorker` (`operations/sync.py`; debug mode stays inline). Browser-sync
  **setup + auto-sync live in Settings** (`ui/settings_dialog.py` Browser Sync
  group -- Set Up/Reinstall, Replace, status, auto-sync toggle). Local edits
  nudge `sync_now()` when auto-sync is on. Config: `[automation]` flat keys
  (`auto_sync`, `interval_minutes`)
  via `config.get/set_automation_config`; paths via `config.automation_dir()`
  etc.
- **Tests**: `test_{protocol,bridge,tree_codec,sync_service,installer}.py` -- all
  pure-Python (no browser). `test_bridge.py` drives a real loopback handshake +
  message round-trip with an in-process client. The real-Chrome hop is manual
  (documented in `docs/browser-sync.md`); everything up to it is verified headless
  (app Bridge <-> frozen `--native-host` handshake confirmed).

## Architecture

- Internal store at `~/.bookmarker/bookmarks.json` is source of truth
- Browsers are "remotes" to import from or push to
- Push replaces entire browser bookmark file
- Sync = import + push (additive-only, no deletions)
- Browser must be closed for write operations
- Chrome/Edge use JSON files with MD5 checksum
- Firefox uses SQLite with safe backup-based reading

## User Interface

### System Tray
- **Single-click**: Opens Quick Launch window for fast bookmark search/launch
- **Double-click**: Opens full Bookmark Editor
- **Right-click**: Context menu with Launch submenu, editor, sync options
- **Add Bookmark from Clipboard**: Creates a new bookmark using clipboard URL

### Quick Launch Window
- Centered popup window for fast bookmark access
- Search box filters bookmarks by title/URL in real-time
- Folder navigation with back/home buttons
- Press Enter to launch selected bookmark
- Press Escape to close
- Clicking a folder navigates into it
- Clicking a bookmark launches it

### Launch Menu (Context Menu)
- Hierarchical submenu showing all bookmarks and folders
- Hover over folders to expand them
- Click a bookmark to open it in the appropriate browser

### Bookmark Launching
- Bookmarks open in the system default browser by default
- Set "Open in" preference per bookmark (Chrome, Edge, Firefox)
- Falls back to default browser if preferred browser not found

## File Watching

- Application watches `~/.bookmarker/bookmarks.json` for external changes
- Uses QFileSystemWatcher with 100ms debounce
- Pauses during self-save to avoid false triggers
- Shows tray notification and refreshes UI on reload

## JSON Import/Export

### Export
- Menu: "Export Bookmarks to JSON..."
- Exports internal store to user-specified JSON file
- Creates a portable backup of all bookmarks

### Import
- Menu: "Import Bookmarks from JSON..."
- Two modes:
  - **Overwrite**: Replace entire store (with confirmation)
  - **Merge**: Add new bookmarks, resolve conflicts
- Preview dialog shows items to add and conflicts
- Conflict detection: Same URL in same folder path
- Backup created before any import

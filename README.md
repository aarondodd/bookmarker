# Bookmarker

A cross-browser bookmark manager for Linux, Windows, and macOS. Bookmarker provides a unified internal store that acts as the single source of truth for your bookmarks, with the ability to import from, push to, and bidirectionally sync with Chrome, Edge, and Firefox.

Runs as a system tray application with a built-in bookmark editor.

## Features

- **Unified bookmark store** at `~/.bookmarker/bookmarks.json` -- one canonical copy of all your bookmarks
- **Import** bookmarks from any combination of Chrome, Edge, and Firefox, with automatic deduplication
- **Push** your bookmark collection to any browser, replacing its bookmarks entirely (eliminating duplicates by design)
- **Bidirectional sync** that computes a plan of changes across store and browser, then executes -- additive-only, so nothing is ever deleted during sync
- **Bookmark editor** with a tree view, folder management, drag-and-drop reordering, and per-bookmark browser preference
- **Dark and light themes** toggled from the tray menu or settings
- **Debug mode** for sync that presents each proposed change individually with Apply / Skip / Apply All Remaining
- **Automatic backups** before every browser write operation, stored in `~/.bookmarker/backups/`
- **Self-updating** via the GitHub Releases API (checks every 7 days, upgrades in-place)

## Supported Browsers

| Browser | Read | Write | Format |
|---|---|---|---|
| Google Chrome | While open | Must be closed | JSON (`Bookmarks`) with MD5 checksum |
| Microsoft Edge | While open | Must be closed | JSON (`Bookmarks`) with MD5 checksum |
| Mozilla Firefox | While open (via SQLite backup API) | Must be closed | SQLite (`places.sqlite`) |

### Browser Bookmark Paths

| Browser | Linux | Windows | macOS |
|---|---|---|---|
| Chrome | `~/.config/google-chrome/Default/Bookmarks` | `%LOCALAPPDATA%/Google/Chrome/User Data/Default/Bookmarks` | `~/Library/Application Support/Google/Chrome/Default/Bookmarks` |
| Edge | `~/.config/microsoft-edge/Default/Bookmarks` | `%LOCALAPPDATA%/Microsoft/Edge/User Data/Default/Bookmarks` | `~/Library/Application Support/Microsoft Edge/Default/Bookmarks` |
| Firefox | `~/.mozilla/firefox/<profile>/places.sqlite` | `%APPDATA%/Mozilla/Firefox/Profiles/<profile>/places.sqlite` | `~/Library/Application Support/Firefox/Profiles/<profile>/places.sqlite` |

Firefox profile detection reads `profiles.ini` to find the default profile automatically.

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/aarondodd/bookmarker.git
cd bookmarker

# Create a virtual environment and install dependencies
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Run the application
.venv/bin/python main.py
```

### Build a Standalone Executable

```bash
# Linux / macOS
./build.sh

# Windows (PowerShell)
.\build.ps1
```

The build script creates a single-file executable using PyInstaller, installs it to `~/bin/bookmarker` (Linux/macOS) or `%USERPROFILE%\bin\bookmarker.exe` (Windows), and ensures `~/bin` exists.

## Dependencies

| Package | Purpose |
|---|---|
| `PyQt6 >= 6.5.0` | GUI framework (system tray, editor, dialogs) |
| `psutil >= 5.9.0` | Detect running browser processes |
| `tomli >= 2.0.0` | TOML config parsing (Python < 3.11 only; 3.11+ uses `tomllib`) |
| `pytest >= 7.0.0` | Test suite |

## Usage

Bookmarker runs as a system tray application. On launch, it loads (or creates) the internal store at `~/.bookmarker/bookmarks.json` and shows a bookmark ribbon icon in the system tray.

### Tray Menu

| Action | Description |
|---|---|
| **Open Editor** | Opens the bookmark editor window (also accessible by double-clicking the tray icon) |
| **Import Bookmarks** | Select browsers to import from; new bookmarks are added, duplicates skipped |
| **Push Bookmarks** | Select browsers to push to; replaces browser bookmarks with the store contents |
| **Sync** | Bidirectional sync with all installed browsers |
| **Settings** | Configure dark mode and debug mode |
| **Toggle Dark/Light Mode** | Quick theme switch |
| **Check for Updates** | Manual check against GitHub Releases |
| **Upgrade** | Download and build the latest release |
| **Exit** | Save and quit |

### Tray Icon States

| State | Appearance | Meaning |
|---|---|---|
| Normal | Dark/light ribbon | Idle |
| Syncing | Blue ribbon | Import, push, or sync in progress |
| Error | Red ribbon | An operation failed |

### Bookmark Editor

The editor opens as a non-modal window with a 40/60 split:

```
Toolbar: [+ Bookmark] [+ Folder] [Delete] [Move Up] [Move Down]
+--------------------------+--------------------------------------+
| Tree View (40%)          | Edit Panel (60%)                     |
|                          |   Title: [_______________]           |
| > Bookmarks Bar          |   URL:   [_______________]           |
|   - Example.com          |   Folder: [dropdown      ]           |
|   > Dev                  |   Open in: [Any browser  ]           |
|     - GitHub             |                                      |
| > Other Bookmarks        |   [Save Changes]                     |
+--------------------------+--------------------------------------+
```

- Select a bookmark in the tree to edit its properties
- Use the toolbar to add bookmarks/folders, delete, or reorder
- The "Open in" dropdown sets a preferred browser for that bookmark
- The "Folder" dropdown lets you move a bookmark to a different folder
- Changes are saved to the internal store immediately

### Import Workflow

1. Right-click tray > **Import Bookmarks**
2. Check the browsers you want to import from (uninstalled browsers are grayed out)
3. Click OK
4. A progress dialog shows status; duplicates are automatically skipped
5. Deduplication key: `(normalized_url, parent_folder_path)` -- the same URL in different folders is kept as separate bookmarks

### Push Workflow

1. Right-click tray > **Push Bookmarks**
2. Check the browsers you want to push to (running browsers show a warning)
3. Close any running target browsers
4. Click OK
5. The store's bookmarks replace the browser's bookmarks entirely
6. For Chrome/Edge: a valid MD5 checksum is calculated and written so the browser accepts the file
7. For Firefox: bookmarks are written into `moz_bookmarks` / `moz_places` tables

### Sync Workflow

1. Right-click tray > **Sync**
2. Bookmarker plans changes for each installed browser:
   - Browser bookmarks not in the store are added to the store
   - Store bookmarks not in the browser are added to the browser
   - If a bookmark exists in both but the browser version is newer, the store is updated
   - Nothing is ever deleted -- sync is additive-only
3. If **debug mode** is enabled (Settings), each change is presented in a confirmation dialog with Apply / Skip / Apply All Remaining
4. Store changes are applied immediately; browser changes are batched and written at the end

### Configuration

Configuration lives in `~/.bookmarker/config.toml`:

```toml
[ui]
dark_mode = false

[sync]
debug_mode = false
```

## Architecture

### Data Model

```
BookmarkStore
  version: 1
  last_modified: ISO 8601 timestamp
  roots:
    bookmark_bar: Bookmark (folder)
    other: Bookmark (folder)

Bookmark
  id: UUID
  type: "url" | "folder"
  title: string
  url: string (empty for folders)
  parent_id: UUID of parent folder
  position: integer (order within parent)
  date_added: ISO 8601
  date_modified: ISO 8601
  preferred_browser: "chrome" | "edge" | "firefox" | null
  source_browser: provenance tracking
  source_id: original ID in source browser
  children: list of Bookmark (for folders)
```

### Folder Mapping

| Internal | Chrome / Edge | Firefox |
|---|---|---|
| `bookmark_bar` | `roots.bookmark_bar` | Bookmarks Toolbar (id=3) |
| `other` | `roots.other` | Bookmarks Menu (id=2) + Other Bookmarks (id=5) |

### Key Design Decisions

- **Store is source of truth.** `~/.bookmarker/bookmarks.json` is the canonical copy. Browsers are treated as remotes.
- **Push replaces entirely.** No appending, no merging on push -- this eliminates duplicates by design.
- **Sync is additive-only.** A bookmark missing from one side is added to the other, never deleted. Deletion only happens through the editor.
- **Browser must be closed for writes.** `psutil` checks for running browser processes and refuses to write if any are found.
- **Always backup first.** Before any browser file modification, the existing file is copied to `~/.bookmarker/backups/` with a timestamp.
- **QThread for all I/O.** Import, push, and sync run in worker threads with `pyqtSignal` for progress reporting.
- **Chromium checksum.** Chrome and Edge require an MD5 checksum calculated over each node's `id` (ASCII), `name` (UTF-16-LE), `type`, and `url` (ASCII), processed depth-first across `bookmark_bar`, `other`, and `synced` roots.
- **Firefox safe read.** Uses `sqlite3.Connection.backup()` to snapshot `places.sqlite` before reading, which works even while Firefox is running.

## Project Structure

```
bookmarker/
  __init__.py
  version.py            # __version__ = "0.1.0"
  app.py                # BookmarkerApp - tray icon, menu, worker orchestration

  models/
    bookmark.py         # Bookmark dataclass, BookmarkStore with CRUD

  operations/
    browser_detect.py   # Detect installed/running browsers, find bookmark paths
    chrome.py           # Chrome JSON reader/writer with MD5 checksum
    edge.py             # Edge (delegates to Chrome with different paths)
    firefox.py          # Firefox SQLite reader/writer with backup-based safe read
    importer.py         # Import orchestrator with dedup and QThread worker
    exporter.py         # Push orchestrator with QThread worker
    sync.py             # Bidirectional sync: plan, execute, debug confirm

  utils/
    config.py           # TOML config at ~/.bookmarker/config.toml
    icon.py             # QPainter bookmark ribbon icon generation
    theme.py            # ThemeManager with dark/light QSS stylesheets
    updater.py          # GitHub Releases API updater for aarondodd/bookmarker

  ui/
    editor.py           # BookmarkEditorWindow (tree + edit panel)
    browser_dialog.py   # Browser selection dialog for import/push
    debug_dialog.py     # Per-change confirmation dialog for sync debug mode
    sync_dialog.py      # Progress dialog for import/push/sync
    settings_dialog.py  # App settings (dark mode, debug mode)

tests/
  conftest.py           # Fixtures: isolated config dir, sample data, sample Chrome JSON
  test_models.py        # 36 tests - Bookmark, BookmarkStore CRUD, serialization
  test_browser_detect.py # 9 tests - browser detection, process checking
  test_chrome.py        # 19 tests - time conversion, checksum, read/write roundtrip
  test_edge.py          # 5 tests - Edge read/write (delegates to Chrome)
  test_firefox.py       # 15 tests - SQLite read/write, time conversion, reverse host
  test_importer.py      # 8 tests - import, dedup, folder merging
  test_exporter.py      # 4 tests - push, running browser check, backup
  test_sync.py          # 10 tests - plan, execute, folder path creation
  test_config.py        # 16 tests - TOML load/save, version check, defaults
  test_icon.py          # 5 tests - icon generation for each state
  test_theme.py         # 6 tests - stylesheet content, dark mode toggle
  test_updater.py       # 14 tests - version parsing, update check, archive extraction
  test_editor.py        # 5 tests - editor window, tree population, refresh
  test_app.py           # 4 tests - app creation, tray, store loading, theme toggle
```

## Testing

```bash
# Run the full test suite (166 tests)
.venv/bin/python -m pytest tests/ -v

# Run a single test file
.venv/bin/python -m pytest tests/test_chrome.py -v

# Run tests matching a pattern
.venv/bin/python -m pytest tests/ -k "sync" -v
```

All tests use an isolated config directory via a `tmp_path` fixture, so no test touches the real `~/.bookmarker/` directory. GUI tests are skipped automatically when no display is available (headless CI).

## Updating

Bookmarker checks for updates automatically on startup (once every 7 days) by querying the GitHub Releases API for `aarondodd/bookmarker`. No authentication is required.

When an update is available:
- A tray notification appears on startup
- **Check for Updates** in the tray menu shows a dialog with the version info
- **Upgrade** downloads the release zip, extracts it, runs the build script, and installs the new executable to `~/bin/`

## License

See repository for license information.

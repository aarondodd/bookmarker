# Bookmarker

Cross-browser bookmark manager with a unified internal store.

## Project Structure

- `main.py` - Entry point
- `bookmarker/` - Main package
  - `app.py` - BookmarkerApp (QMainWindow + system tray)
  - `version.py` - Version string
  - `models/bookmark.py` - Bookmark dataclass + BookmarkStore
  - `operations/` - Browser I/O (chrome, edge, firefox, sync, importer, exporter)
  - `utils/` - Config, icon, theme, updater, launcher
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

# Build executable
./build.sh
```

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

# Bookmarker

Cross-browser bookmark manager with a unified internal store.

## Project Structure

- `main.py` - Entry point
- `bookmarker/` - Main package
  - `app.py` - BookmarkerApp (QMainWindow + system tray)
  - `version.py` - Version string
  - `models/bookmark.py` - Bookmark dataclass + BookmarkStore
  - `operations/` - Browser I/O (chrome, edge, firefox, sync, importer, exporter)
  - `utils/` - Config, icon, theme, updater
  - `ui/` - Editor, dialogs
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

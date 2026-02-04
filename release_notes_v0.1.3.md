# Release Notes - Bookmarker v0.1.3

## New Features

### File Watching
The application now automatically detects when `bookmarks.json` is modified externally (e.g., by another instance, a script, or manual editing). When an external change is detected:
- The store is automatically reloaded
- A tray notification informs you of the reload
- The editor window (if open) is refreshed
- Uses debouncing (100ms) to handle rapid changes gracefully

### JSON Import/Export
New menu options for portable bookmark backup and sharing:

**Export Bookmarks to JSON...**
- Export your entire bookmark collection to a JSON file
- Choose any location and filename
- Creates a portable backup you can share or archive

**Import Bookmarks from JSON...**
- Import bookmarks from a previously exported JSON file
- Two import modes:
  - **Merge**: Add new bookmarks while preserving existing ones
    - Detects duplicates (same URL in same folder)
    - Shows preview dialog with items to be added
    - Identifies conflicts (same URL, different title) for resolution
    - Choose to keep existing or use imported for each conflict
  - **Overwrite**: Replace all bookmarks with the imported file
    - Requires confirmation
    - Creates automatic backup before overwriting
- Automatic backup created before any import operation

## Technical Details

### New Files
- `bookmarker/utils/file_watcher.py` - QFileSystemWatcher wrapper with debounce
- `bookmarker/operations/store_export.py` - Export/import logic with conflict detection
- `bookmarker/ui/import_mode_dialog.py` - Mode selection dialog
- `bookmarker/ui/import_preview_dialog.py` - Preview and conflict resolution dialog
- `tests/test_file_watcher.py` - File watcher tests
- `tests/test_store_export.py` - Import/export tests

### Modified Files
- `bookmarker/app.py` - Integrated file watcher and import/export handlers
- `CLAUDE.md` - Updated documentation

## Testing
All 220 tests pass, including 18 new tests for the file watcher and import/export functionality.

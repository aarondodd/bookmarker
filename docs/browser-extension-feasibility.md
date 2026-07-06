# Feasibility: a browser extension for live bookmark sync

> **Status: IMPLEMENTED (Chromium) as of 2026-07-06.** This study's recommended
> architecture was built -- see `docs/browser-sync.md` for the user/dev guide and
> `bookmarker/automation/` + `bookmarker/resources/extension/` for the code. This
> document is retained as the design rationale.


## Why this exists

Bookmarker's current model treats each browser as a file it reads and rewrites:
Chrome/Edge `Bookmarks` JSON, Firefox `places.sqlite`. That is why every write
operation requires the browser to be **closed**. A running browser owns its
bookmark store in memory, holds a lock (Firefox) or an in-memory copy it flushes
on exit (Chromium), and will happily clobber whatever Bookmarker wrote the moment
it shuts down. So "push" and "sync" today are offline operations.

The question this document answers: **can we keep a *running* browser in sync with
Bookmarker, and if so, how?** Short answer -- yes, via a browser extension talking
to the Bookmarker app over Native Messaging. This is the only supported way to
mutate a live browser's bookmarks, and it is the same architecture the
meeting-notetaker project already uses for its synthesis bridge
(`projects/meeting-notetaker/meeting_notetaker/resources/extension/`).

## The one API that changes everything

Every major browser exposes a **WebExtensions bookmarks API** to installed
extensions:

- Chrome / Edge (Manifest V3): `chrome.bookmarks`
- Firefox: `browser.bookmarks` (same surface, plus separators)

It provides live, in-process read/write against the running browser:

| Need | API |
|---|---|
| Read the whole tree | `bookmarks.getTree()`, `getSubTree()`, `getChildren()` |
| Create a folder/bookmark | `bookmarks.create({parentId, title, url, index})` |
| Move / reorder | `bookmarks.move(id, {parentId, index})` |
| Rename / re-point | `bookmarks.update(id, {title, url})` |
| Delete | `bookmarks.remove(id)`, `removeTree(id)` |
| React to user edits | `onCreated`, `onChanged`, `onMoved`, `onRemoved` events |
| Periodic wakeups | `alarms` API |

This closes the exact gap the file-based approach cannot: an extension can edit
bookmarks while the browser is open, and it gets notified when the user edits
them by hand.

## Architecture

```
+-------------------+        Native Messaging (stdio JSON)        +--------------------+
|  Browser          |  <---------------------------------------> |  Bookmarker app     |
|  extension        |                                            |  (--native-host)    |
|                   |                                            |                    |
|  background SW     |   getTree / create / move / remove         |  reconcile against  |
|  + chrome.bookmarks|   + onCreated/onChanged/... events         |  ~/.bookmarker/     |
|  + alarms          |                                            |  bookmarks.json     |
+-------------------+                                            +--------------------+
```

- **Extension side**: an unpacked MV3 extension (Chrome/Edge) and a Firefox
  WebExtension. A background service worker owns the `chrome.bookmarks` calls,
  subscribes to the change events, and runs an `alarms`-driven periodic sync.
- **App side**: Bookmarker gains a `--native-host` entrypoint that speaks the
  Native Messaging stdio protocol (4-byte length prefix + JSON message). It maps
  extension requests onto the existing store (`bookmarker/models/bookmark.py`)
  and the reconciliation engine (`bookmarker/operations/sync.py`). No new sync
  algorithm is needed -- `plan_sync` / `execute_sync` already computes additive
  deltas; the extension just replaces the file reader/writer as the transport to
  the browser.
- **Transport**: Native Messaging, requested via the `nativeMessaging` permission
  (exactly as in meeting-notetaker's `manifest.json`). The app registers a
  *native messaging host manifest* -- a small JSON file pointing at the Bookmarker
  executable, with `allowed_origins` pinned to the extension's ID -- in the
  per-browser, per-OS location the browser scans at startup.

### Native-host manifest locations (host app writes these on install/enable)

| Browser | Linux | Windows |
|---|---|---|
| Chrome | `~/.config/google-chrome/NativeMessagingHosts/` | registry `HKCU\Software\Google\Chrome\NativeMessagingHosts\<name>` -> manifest path |
| Edge | `~/.config/microsoft-edge/NativeMessagingHosts/` | registry `HKCU\Software\Microsoft\Edge\NativeMessagingHosts\<name>` |
| Firefox | `~/.mozilla/native-messaging-hosts/` | registry `HKCU\Software\Mozilla\NativeMessagingHosts\<name>` |

Bookmarker already computes per-OS browser paths in
`bookmarker/operations/browser_detect.py`; the host-manifest install reuses the
same platform branches.

## The two flows the user asked for

### 1. Replace (push the whole collection)

Goal: make the browser exactly match Bookmarker's store, dropping browser-only
bookmarks. With the extension this is straightforward and, unlike today, works
while the browser is open:

1. App sends the full store tree to the extension.
2. Extension calls `getTree()`, then `removeTree()` on each child of the roots
   (Bookmarks Bar / Other), i.e. wipes the existing tree.
3. Extension recreates the tree from the store payload via `create()` calls,
   depth-first, preserving order via the `index` argument.
4. Extension reports the new browser-node-id for each created item back to the
   app, which persists an id mapping (see below).

This is the safe direction: it is deterministic and needs no conflict handling.
It is the recommended first milestone.

### 2. Regular bidirectional sync

Goal: keep both sides converged continuously. Event-driven, both directions:

- **Browser -> store**: the service worker's `onCreated/onChanged/onMoved/
  onRemoved` handlers debounce and forward deltas to the app, which applies them
  to `bookmarks.json` (additive by default, matching today's sync semantics).
- **Store -> browser**: when the app's file watcher
  (`bookmarker/utils/file_watcher.py`) sees the store change, it pushes the
  affected deltas to the extension, which applies them with `create/move/update`.
- **Periodic reconcile**: an `alarms` tick triggers a full `getTree()` diff
  against the store to heal any missed events (service workers can be evicted).

## The hard parts (and how to handle them)

- **Stable identity across the replace.** Browser node IDs are assigned by the
  browser, are not portable between browsers, and are regenerated whenever the
  tree is recreated (flow 1 changes every ID). Bookmarker's store already has
  stable GUIDs (`Bookmark.id`) plus a `source_browser`/`source_id` pair. The
  extension must persist a **mapping table** (store GUID <-> browser node ID) in
  `chrome.storage.local`, rebuilt after every replace and updated as create
  events fire. When an event arrives with an unknown node ID, fall back to
  matching on (normalized URL + folder path) -- the same key
  `operations/sync.py::_build_lookup` already uses.
- **Conflict resolution.** Today's engine is additive-only (never deletes during
  sync). Live sync raises real conflicts (same bookmark edited on both sides
  between ticks). Start additive + last-writer-wins on title/URL using the
  existing `date_modified` comparison in `plan_sync`; defer true 3-way merge.
- **Firefox specifics.** `browser.bookmarks` exposes separators and (historically)
  keywords that the Chromium model lacks; map separators to a store folder-less
  marker or ignore them in v1.
- **Service-worker lifecycle (MV3).** The background worker is not persistent;
  it can be killed between events. Rely on `alarms` to re-establish the native
  port and run the periodic full reconcile rather than assuming a long-lived
  connection.

## Distribution reality (the real friction, not the code)

The code is the easy part; getting the extension *installed and staying enabled*
is the friction, and it is browser-specific:

- **Chrome / Edge**: an unpacked extension loaded via `chrome://extensions`
  developer mode works for personal use but shows a "disable developer mode
  extensions" nag on each launch and can be auto-disabled. Durable options are
  the Chrome Web Store / Edge Add-ons (review + a developer account) or an
  enterprise `ExtensionInstallForcelist` policy on a machine you control.
  meeting-notetaker ships the unpacked extension inside the app bundle and has
  the user load it once -- an acceptable tradeoff for a personal tool, and the
  recommended path here too.
- **Firefox**: extensions must be signed by Mozilla (AMO) to install permanently
  in release/ESR; unsigned loads only in Developer Edition / Nightly or via an
  ESR enterprise policy. Firefox support is therefore a later milestone than
  Chromium.
- **Native host security**: `allowed_origins` in the host manifest pins the
  extension ID, and the extension `key` in the manifest pins that ID across
  machines (meeting-notetaker does exactly this with a fixed `key`). Both must be
  generated once and kept stable.

## Verdict

Feasible, and it is the correct architecture -- it removes the "close the browser
first" limitation that the file-based design fundamentally cannot. The heavy
lifting is not the browser API (which is small and well-documented) but two
things: the native-host handshake/registration per OS+browser, and stable ID
mapping for true bidirectional sync. Both are tractable and mostly reuse code
that already exists in Bookmarker and meeting-notetaker.

### Recommended phasing

1. **Native-host handshake** -- add the `--native-host` stdio entrypoint and
   host-manifest registration; prove a round-trip ping with an unpacked
   Chrome/Edge extension.
2. **Replace-only** -- implement flow 1 (wipe + recreate from store) end to end,
   with the id-mapping table. Highest value, lowest risk; delivers "replace the
   browser's bookmarks with Bookmarker's" against a *running* browser.
3. **Event-driven sync** -- add the change-event handlers + `alarms` reconcile
   for continuous bidirectional sync, reusing `operations/sync.py`.
4. **Firefox + distribution** -- port to `browser.bookmarks`, then tackle AMO
   signing / Web Store submission as needed.

### Reuse map

- Extension skeleton + Native Messaging wiring: `projects/meeting-notetaker/
  meeting_notetaker/resources/extension/{manifest.json,background.js}` (the
  `nativeMessaging` permission, background service worker, and stable `key`).
- Store model + reconciliation core: `bookmarker/models/bookmark.py`
  (`BookmarkStore`, stable GUIDs, `find_by_url`, `normalize_url`) and
  `bookmarker/operations/sync.py` (`plan_sync` / `execute_sync`, the additive
  delta engine and the (url, root, path) lookup key).
- Per-OS path logic for host-manifest install:
  `bookmarker/operations/browser_detect.py`.

## Out of scope for this document

No extension code is written here -- this is a feasibility study. Building the
native host, the extension, and the id-mapping layer is the follow-up work
outlined in the phasing above.

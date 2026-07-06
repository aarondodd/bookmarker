# Browser Sync (live)

Keeps a **running** Chrome/Edge browser's bookmarks in sync with Bookmarker's
store -- something the file-based import/push/sync cannot do (those require the
browser closed). A small MV3 extension talks to the Bookmarker app over Native
Messaging; the app reconciles changes against `~/.bookmarker/bookmarks.json`.

This is the Chromium implementation of the design in
`browser-extension-feasibility.md`.

## Architecture

```
extension (chrome.bookmarks)  <-- native messaging (stdio) -->  native host
        ^                                                            |
        | chrome.bookmarks events / apply                           | TCP loopback
        v                                                            v
   running browser                                        Bookmarker app (Bridge)
                                                                     |
                                                          ~/.bookmarker/bookmarks.json
```

- **Extension** (`bookmarker/resources/extension/`): MV3 service worker using the
  `bookmarks`, `nativeMessaging`, `storage`, `alarms` permissions. It pushes a
  full tree snapshot on any bookmark change (debounced) and on a periodic alarm,
  and applies `replace` / `apply_ops` the app sends back.
- **Native host** (`bookmarker/automation/native_host.py`, run via
  `bookmarker --native-host`): a thin stdio<->TCP relay Chrome spawns. It reads
  `~/.bookmarker/automation/bridge.json` (loopback port + per-launch token) to
  reach the running app.
- **App** (`bookmarker/automation/`): `bridge.py` is the loopback TCP server;
  `sync_service.py` reconciles; `controller.py` is the Qt glue driving replace/
  sync; `installer.py` extracts the extension + registers the native host.

## Setup (one time)

1. In the Bookmarker tray menu, choose **Browser Sync (live)...**
2. Click **Set Up / Reinstall**. This extracts the extension to
   `~/.bookmarker/automation/extension/` and registers the native-messaging host
   (per-browser manifest on Linux/macOS; HKCU registry on Windows).
3. Load the extension once in your browser:
   - Open `chrome://extensions` (or `edge://extensions`)
   - Enable **Developer mode**
   - **Load unpacked** -> select `~/.bookmarker/automation/extension/`
4. The dialog shows **Browser: connected** once the extension links up.

The extension ID is pinned (`cckjffdjcffgggmdjamiabnpebegdmcg`) via a fixed
manifest `key`, and the native host's `allowed_origins` is pinned to it, so only
this extension can drive the host.

## Using it

- **Replace Browser with Bookmarker's** -- wipes the browser's Bookmarks Bar +
  Other Bookmarks and recreates them from the store. Full one-way mirror.
- **Sync Now** -- one reconcile pass.
- **Automatic sync** -- toggle + interval (default 15 min). Also runs on connect
  and whenever you edit bookmarks in either the app or the browser.

## How sync resolves changes

Sync matches items by structure -- `(root, folder path, normalized URL)` for
bookmarks, `(root, folder path)` for folders -- not by browser node id (those are
unstable). A per-browser baseline (`~/.bookmarker/automation/idmap-<browser>.json`)
records what was synced last pass. From that:

- **Additions** propagate both ways.
- **Title conflicts** on the same URL use a 3-way merge against the baseline:
  whichever side changed wins; if both changed, the store (Bookmarker) wins.
- **Deletions mirror both ways, gated by the baseline.** An item removed on one
  side is removed on the other **only if it was in the baseline** (i.e. it had
  been synced before). Items that were never synced are added, never deleted --
  so nothing you simply hadn't synced yet gets nuked.

## Firefox

The extension code is written portably (`chrome.*`/`browser.*` aliased), but this
build is only tested on Chromium (Chrome/Edge). Firefox needs an AMO-signed build
to install permanently and is not verified here.

## Troubleshooting

- **Browser: not connected** -- make sure the Bookmarker app is running (the host
  reads `bridge.json`, which only exists while the app is up), then click
  **Reconnect** in the extension popup or re-open the browser.
- **Nothing syncs after setup** -- confirm the unpacked extension is loaded and
  enabled at `chrome://extensions`, and that **Set Up / Reinstall** was run so the
  native host manifest exists.
- **Reset the baseline** -- delete `~/.bookmarker/automation/idmap-<browser>.json`
  and run **Replace** to re-establish a clean baseline.

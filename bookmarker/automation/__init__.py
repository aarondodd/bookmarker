"""Browser-sync automation: native-messaging bridge between Bookmarker and a
running Chrome/Edge browser extension.

Layers:
- ``protocol``    -- length-prefixed JSON wire framing (both hops).
- ``bridge``      -- app-side loopback TCP server the native host connects to.
- ``native_host`` -- the ``--native-host`` stdio<->TCP bridge Chrome spawns.
- ``messages``    -- the app<->extension message schema.
- ``tree_codec``  -- BookmarkStore <-> browser-tree JSON conversion.
- ``sync_service``-- two-way reconciliation + ID-map persistence.
- ``installer``   -- extract the extension + register the native host per OS.
- ``controller``  -- Qt glue (owns the Bridge, drives replace/sync).
"""

"""Qt-side glue for browser sync.

Owns the :class:`~bookmarker.automation.bridge.Bridge`, re-marshals bridge-thread
callbacks onto the Qt main thread via signals, and drives the sync flows:

- ``replace()``   -- push the whole store onto the browser (wipe + recreate).
- ``sync_now()``  -- request the browser tree, reconcile, apply the delta both
  ways, persist the baseline.
- an auto-sync ``QTimer`` runs ``sync_now`` on an interval when enabled.

Every trigger converges on the same path: get the browser tree ->
``sync_service.reconcile`` -> apply ops to the browser + mutate the store. The
store is authoritative on title conflicts; deletions mirror both ways gated by
the baseline (see ``sync_service``).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from ..models.bookmark import BookmarkStore
from ..utils.config import bridge_handshake_path
from ..version import __version__
from . import messages, sync_service
from .bridge import Bridge, HandshakeState

log = logging.getLogger(__name__)


class BrowserSyncController(QObject):
    """Drives the native-messaging bridge and the sync flows. Lives on the Qt
    main thread; the owning app connects to its signals."""

    connection_changed = pyqtSignal(bool)  # connected?
    status = pyqtSignal(str)               # human-readable status line
    store_updated = pyqtSignal()           # store changed by an inbound sync
    sync_finished = pyqtSignal(str)        # a reconcile pass completed; summary

    # Internal: marshal a bridge-thread message onto the main thread.
    _inbound = pyqtSignal(dict)
    _connect_evt = pyqtSignal(bool)

    def __init__(self, store: BookmarkStore, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.store = store
        self._peer_browser = "chrome"
        self._bridge = Bridge(
            bridge_handshake_path(),
            on_message=lambda m: self._inbound.emit(m),
            on_connect=lambda s: self._connect_evt.emit(True),
            on_disconnect=lambda: self._connect_evt.emit(False),
            app_version=__version__,
        )
        self._inbound.connect(self._handle_message)
        self._connect_evt.connect(self._handle_connection)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.sync_now)

    # ------------------------------------------------------------------ lifecycle

    def start(self) -> None:
        self._bridge.start()

    def stop(self) -> None:
        self._timer.stop()
        self._bridge.stop()

    def set_auto_sync(self, enabled: bool, interval_minutes: int = 15) -> None:
        if enabled:
            self._timer.start(max(1, interval_minutes) * 60_000)
        else:
            self._timer.stop()

    @property
    def is_connected(self) -> bool:
        return self._bridge.is_connected

    # ------------------------------------------------------------------ flows

    def replace(self) -> bool:
        """Wipe the connected browser's bookmarks and recreate them from the
        store. Seeds the baseline so the next reconcile treats them as synced."""
        if not self._bridge.is_connected:
            self.status.emit("No browser connected. Load the extension and try again.")
            return False
        payload = sync_service.build_replace_payload(self.store)
        ok = self._bridge.send(messages.replace(payload, request_id=uuid.uuid4().hex))
        if ok:
            sync_service.save_baseline(
                self._peer_browser, sync_service.baseline_from_store(self.store)
            )
            self.status.emit("Replaced browser bookmarks with Bookmarker's.")
        return ok

    def sync_now(self) -> bool:
        """Request the browser tree; reconciliation happens when it arrives."""
        if not self._bridge.is_connected:
            return False
        return self._bridge.send(messages.request_tree(request_id=uuid.uuid4().hex))

    def ping(self) -> bool:
        if not self._bridge.is_connected:
            return False
        return self._bridge.send(messages.ping(request_id=uuid.uuid4().hex))

    # ------------------------------------------------------------------ inbound

    def _handle_connection(self, connected: bool) -> None:
        self.connection_changed.emit(connected)
        self.status.emit("Browser connected." if connected else "Browser disconnected.")
        if connected:
            # Establish current state on connect.
            self.sync_now()

    def _handle_message(self, msg: Dict[str, Any]) -> None:
        mtype = msg.get("type")
        if mtype == messages.PONG:
            self._peer_browser = msg.get("browser") or self._peer_browser
            self.status.emit(f"Extension v{msg.get('extension_version', '?')} reachable.")
        elif mtype == messages.TREE:
            self._peer_browser = msg.get("browser") or self._peer_browser
            self._on_tree(msg)
        elif mtype == messages.ERROR:
            self.status.emit(f"Extension error: {msg.get('detail', msg.get('code', ''))}")
        elif mtype == messages.BRIDGE_READY:
            log.info("bridge ready (app_version=%s)", msg.get("app_version"))

    def _on_tree(self, msg: Dict[str, Any]) -> None:
        nodes = msg.get("nodes", [])
        baseline = sync_service.load_baseline(self._peer_browser)
        result = sync_service.reconcile(self.store, nodes, baseline)
        if result.ops:
            self._bridge.send(messages.apply_ops(result.ops, request_id=uuid.uuid4().hex))
        sync_service.save_baseline(self._peer_browser, result.baseline)
        if result.store_changed:
            self.store.save()
            self.store_updated.emit()
        summary = (
            f"Synced: {len(result.ops)} browser change(s)"
            f"{', store updated' if result.store_changed else ''}."
        )
        self.status.emit(summary)
        self.sync_finished.emit(summary)

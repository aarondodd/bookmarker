"""Message schema exchanged between the app, the native host, and the extension.

Wire format is JSON dicts (framed by ``protocol``). The same dict shape flows
over both hops. Every message carries a ``type`` discriminator; request/response
pairs carry a ``request_id`` so the app can match replies to the call that
produced them.

Node shape (used inside ``replace`` payloads and ``tree`` snapshots)::

    {
      "store_id": "<Bookmark.id>" | null,   # app-assigned GUID (may be null)
      "node_id":  "<browser node id>" | null,  # browser-assigned (may be null)
      "title":    str,
      "url":      str,      # "" for folders
      "index":    int,
      "is_folder": bool,
      "children": [ ...nodes... ]   # folders only
    }

Op shape (inside ``apply_ops`` app->ext, and mirrored by ``events`` ext->app):
    create: {action, store_id, parent_node_id, index, title, url, is_folder}
    update: {action, node_id, title, url}
    move:   {action, node_id, parent_node_id, index}
    remove: {action, node_id}
"""
from __future__ import annotations

from typing import Any

# --- transport (native host <-> app) ---------------------------------------
HANDSHAKE = "handshake"
HANDSHAKE_ACK = "handshake_ack"
BRIDGE_READY = "bridge_ready"

# --- app -> extension ------------------------------------------------------
PING = "ping"
REPLACE = "replace"
APPLY_OPS = "apply_ops"
REQUEST_TREE = "request_tree"

# --- extension -> app ------------------------------------------------------
PONG = "pong"
TREE = "tree"
EVENTS = "events"
APPLY_RESULT = "apply_result"
ERROR = "error"

# op / event actions
ACTION_CREATE = "create"
ACTION_UPDATE = "update"
ACTION_MOVE = "move"
ACTION_REMOVE = "remove"


# --- builders (app side) ---------------------------------------------------


def ping(request_id: str = "") -> dict[str, Any]:
    return {"type": PING, "request_id": request_id}


def replace(tree: list[dict[str, Any]], request_id: str = "") -> dict[str, Any]:
    """Ask the extension to wipe the browser's bookmark roots and recreate them
    from ``tree`` (a list of per-root node dicts)."""
    return {"type": REPLACE, "request_id": request_id, "tree": tree}


def apply_ops(ops: list[dict[str, Any]], request_id: str = "") -> dict[str, Any]:
    """Ask the extension to apply an ordered list of create/update/move/remove
    operations to the running browser."""
    return {"type": APPLY_OPS, "request_id": request_id, "ops": ops}


def request_tree(request_id: str = "") -> dict[str, Any]:
    """Ask the extension for a full ``getTree`` snapshot."""
    return {"type": REQUEST_TREE, "request_id": request_id}


# --- builders (host/app transport) -----------------------------------------


def handshake_ack(*, accepted: bool, app_version: str, detail: str = "") -> dict[str, Any]:
    return {
        "type": HANDSHAKE_ACK,
        "accepted": accepted,
        "app_version": app_version,
        "detail": detail,
    }


def error(code: str, detail: str = "") -> dict[str, Any]:
    return {"type": ERROR, "code": code, "detail": detail}

// Bookmarker Sync -- background service worker.
//
// Bridges chrome.bookmarks <-> the Bookmarker desktop app over a native-
// messaging port (host: org.aarondodd.bookmarker.sync). The host is a thin
// stdio<->TCP relay to the running app.
//
// Flows (all converge on a full-tree reconcile the app computes):
//   * app -> ext:  ping / replace{tree} / apply_ops{ops} / request_tree
//   * ext -> app:  pong / tree{nodes} (full snapshot) / error
// Local bookmark edits and a periodic alarm both push a fresh tree{nodes}
// snapshot; the app reconciles it against its store and replies with apply_ops.
//
// Firefox exposes the same API under `browser.*`; we alias so one file works on
// both, though this build targets Chromium.

const api = (typeof browser !== "undefined") ? browser : chrome;

const NATIVE_HOST = "org.aarondodd.bookmarker.sync";
const EXTENSION_VERSION = api.runtime.getManifest().version;
const RECONNECT_ALARM = "bookmarker-reconnect";
const SYNC_ALARM = "bookmarker-sync";
const SNAPSHOT_DEBOUNCE_MS = 800;

// Chromium root folder ids. "1" = Bookmarks Bar, "2" = Other Bookmarks.
const ROOT_IDS = { bookmark_bar: "1", other: "2" };

let port = null;
// While we are applying app-driven changes, ignore our own change events so we
// don't ping-pong snapshots back at the app.
let suppressUntil = 0;
let snapshotTimer = null;

function browserLabel() {
  const ua = (self.navigator && self.navigator.userAgent) || "";
  if (/Edg\//.test(ua)) return "edge";
  if (/OPR\//.test(ua)) return "opera";
  return "chrome";
}

// --------------------------------------------------------------------- port

function ensurePort() {
  if (port) return port;
  try {
    port = api.runtime.connectNative(NATIVE_HOST);
  } catch (e) {
    console.warn("connectNative failed:", e);
    port = null;
    return null;
  }
  port.onMessage.addListener(handleAppMessage);
  port.onDisconnect.addListener(() => {
    const err = api.runtime.lastError;
    if (err) console.warn("native host disconnected:", err.message);
    port = null;
    // Retry shortly; the app may not be running yet.
    api.alarms.create(RECONNECT_ALARM, { delayInMinutes: 0.5 });
  });
  return port;
}

function sendToApp(payload) {
  const p = ensurePort();
  if (!p) return false;
  try {
    p.postMessage(payload);
    return true;
  } catch (e) {
    console.warn("postMessage failed:", e);
    port = null;
    return false;
  }
}

// --------------------------------------------------------------------- app -> ext

async function handleAppMessage(msg) {
  if (!msg || typeof msg !== "object") return;
  switch (msg.type) {
    case "bridge_ready":
      // Announce ourselves so the app knows the extension version.
      sendToApp({ type: "pong", request_id: "", extension_version: EXTENSION_VERSION, browser: browserLabel() });
      return;
    case "ping":
      sendToApp({ type: "pong", request_id: msg.request_id || "", extension_version: EXTENSION_VERSION, browser: browserLabel() });
      return;
    case "request_tree":
      await sendSnapshot();
      return;
    case "replace":
      await doReplace(msg.tree || []);
      return;
    case "apply_ops":
      await applyOps(msg.ops || []);
      return;
    case "error":
      console.warn("app error:", msg);
      return;
    default:
      console.warn("unhandled app message:", msg.type);
  }
}

// --------------------------------------------------------------------- snapshot (ext -> app)

async function buildSnapshot() {
  const roots = [];
  for (const [rootName, rootId] of Object.entries(ROOT_IDS)) {
    let children = [];
    try {
      children = await api.bookmarks.getChildren(rootId);
    } catch (e) {
      children = [];
    }
    const nodes = [];
    for (const c of children) nodes.push(await nodeToJson(c));
    roots.push({ root: rootName, node_id: rootId, children: nodes });
  }
  return roots;
}

async function nodeToJson(node) {
  const isFolder = !node.url;
  const out = {
    node_id: node.id,
    title: node.title || "",
    url: node.url || "",
    is_folder: isFolder,
  };
  if (isFolder) {
    const kids = await api.bookmarks.getChildren(node.id).catch(() => []);
    out.children = [];
    for (const k of kids) out.children.push(await nodeToJson(k));
  }
  return out;
}

async function sendSnapshot() {
  const nodes = await buildSnapshot();
  sendToApp({ type: "tree", request_id: "", browser: browserLabel(), nodes });
}

function scheduleSnapshot() {
  if (Date.now() < suppressUntil) return;
  if (snapshotTimer) clearTimeout(snapshotTimer);
  snapshotTimer = setTimeout(() => { snapshotTimer = null; sendSnapshot(); }, SNAPSHOT_DEBOUNCE_MS);
}

// --------------------------------------------------------------------- replace / ops (app -> browser)

async function doReplace(tree) {
  suppressUntil = Date.now() + 10_000;
  for (const entry of tree) {
    const rootId = ROOT_IDS[entry.root];
    if (!rootId) continue;
    const children = await api.bookmarks.getChildren(rootId).catch(() => []);
    for (const c of children) {
      await (c.url ? api.bookmarks.remove(c.id) : api.bookmarks.removeTree(c.id)).catch(() => {});
    }
    for (const node of entry.children || []) await createNode(rootId, node);
  }
  suppressUntil = Date.now() + 2_000;
  await sendSnapshot();
}

async function createNode(parentId, node) {
  if (node.is_folder) {
    const folder = await api.bookmarks.create({ parentId, title: node.title || "" });
    for (const child of node.children || []) await createNode(folder.id, child);
  } else {
    await api.bookmarks.create({ parentId, title: node.title || "", url: node.url }).catch(() => {});
  }
}

async function applyOps(ops) {
  suppressUntil = Date.now() + 10_000;
  for (const op of ops) {
    const rootId = ROOT_IDS[op.root];
    if (!rootId) continue;
    try {
      if (op.action === "create") {
        const parentId = await resolvePath(rootId, op.path || [], true);
        if (!parentId) continue;
        if (op.is_folder) await ensureFolder(parentId, op.title);
        else await api.bookmarks.create({ parentId, title: op.title || "", url: op.url });
      } else if (op.action === "update") {
        const parentId = await resolvePath(rootId, op.path || [], false);
        if (!parentId) continue;
        const node = await findChildByUrl(parentId, op.url);
        if (node) await api.bookmarks.update(node.id, { title: op.title || "" });
      } else if (op.action === "remove") {
        const parentId = await resolvePath(rootId, op.path || [], false);
        if (!parentId) continue;
        if (op.is_folder) {
          const f = await findFolder(parentId, op.title);
          if (f) await api.bookmarks.removeTree(f.id).catch(() => {});
        } else {
          const n = await findChildByUrl(parentId, op.url);
          if (n) await api.bookmarks.remove(n.id).catch(() => {});
        }
      }
    } catch (e) {
      console.warn("op failed:", op, e);
    }
  }
  suppressUntil = Date.now() + 2_000;
}

async function resolvePath(rootId, path, create) {
  let parentId = rootId;
  for (const part of path) {
    let folder = await findFolder(parentId, part);
    if (!folder) {
      if (!create) return null;
      folder = await api.bookmarks.create({ parentId, title: part });
    }
    parentId = folder.id;
  }
  return parentId;
}

async function ensureFolder(parentId, title) {
  const existing = await findFolder(parentId, title);
  if (existing) return existing;
  return api.bookmarks.create({ parentId, title });
}

async function findFolder(parentId, title) {
  const kids = await api.bookmarks.getChildren(parentId).catch(() => []);
  return kids.find((k) => !k.url && k.title === title) || null;
}

async function findChildByUrl(parentId, url) {
  const kids = await api.bookmarks.getChildren(parentId).catch(() => []);
  const target = normalizeUrl(url);
  return kids.find((k) => k.url && normalizeUrl(k.url) === target) || null;
}

// Mirror of Python normalize_url (models/bookmark.py): lowercase scheme+host,
// strip trailing slash from path, drop fragment.
function normalizeUrl(url) {
  if (!url) return "";
  try {
    const u = new URL(url);
    const scheme = u.protocol.replace(":", "").toLowerCase();
    const host = u.host.toLowerCase();
    let path = u.pathname || "";
    if (path.endsWith("/")) path = path.slice(0, -1);
    return host ? `${scheme}://${host}${path}` : url;
  } catch (e) {
    return url;
  }
}

// --------------------------------------------------------------------- events + wiring

for (const evt of ["onCreated", "onChanged", "onMoved", "onRemoved"]) {
  if (api.bookmarks[evt]) api.bookmarks[evt].addListener(() => scheduleSnapshot());
}

api.runtime.onStartup.addListener(() => { ensurePort(); });
api.runtime.onInstalled.addListener(() => { ensurePort(); });

api.alarms.create(SYNC_ALARM, { periodInMinutes: 15 });
api.alarms.onAlarm.addListener((alarm) => {
  ensurePort();
  if (alarm.name === SYNC_ALARM) sendSnapshot();
});

// Popup -> background commands.
api.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    if (msg && msg.cmd === "status") {
      sendResponse({ connected: !!port, browser: browserLabel(), version: EXTENSION_VERSION });
    } else if (msg && msg.cmd === "sync") {
      await sendSnapshot();
      sendResponse({ ok: true });
    } else if (msg && msg.cmd === "connect") {
      ensurePort();
      sendResponse({ ok: !!port });
    }
  })();
  return true; // async response
});

// Kick a connection attempt on load.
ensurePort();

// Bookmarker Sync popup: show connection status and offer sync / reconnect.
const api = (typeof browser !== "undefined") ? browser : chrome;

const statusEl = document.getElementById("status");

function render(state) {
  if (state && state.connected) {
    statusEl.className = "status ok";
    statusEl.textContent = `Connected to Bookmarker (${state.browser}, ext v${state.version}).`;
  } else {
    statusEl.className = "status bad";
    statusEl.textContent = "Not connected. Is the Bookmarker app running?";
  }
}

function refresh() {
  api.runtime.sendMessage({ cmd: "status" }, render);
}

document.getElementById("sync").addEventListener("click", () => {
  api.runtime.sendMessage({ cmd: "sync" }, () => setTimeout(refresh, 400));
});

document.getElementById("reconnect").addEventListener("click", () => {
  api.runtime.sendMessage({ cmd: "connect" }, () => setTimeout(refresh, 400));
});

refresh();

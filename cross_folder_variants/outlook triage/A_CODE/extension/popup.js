const dot = document.getElementById("dot");
const statusEl = document.getElementById("status");
const urlInput = document.getElementById("url");

function updateUI(connected) {
  dot.className = connected ? "dot connected" : "dot disconnected";
  statusEl.className = connected ? "status ok" : "status err";
  statusEl.textContent = connected ? "Connected to agent" : "Not connected";
}

chrome.runtime.sendMessage({ type: "status" }, (response) => {
  if (response) {
    updateUI(response.connected);
    if (response.url) urlInput.value = response.url;
  }
});

document.getElementById("connect").addEventListener("click", () => {
  chrome.runtime.sendMessage(
    { type: "connect", url: urlInput.value },
    () => {
      setTimeout(() => {
        chrome.runtime.sendMessage({ type: "status" }, (r) => updateUI(r?.connected));
      }, 1500);
    }
  );
});

document.getElementById("disconnect").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "disconnect" }, () => updateUI(false));
});

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "agent_connected") updateUI(true);
  if (msg.type === "agent_disconnected") updateUI(false);
});

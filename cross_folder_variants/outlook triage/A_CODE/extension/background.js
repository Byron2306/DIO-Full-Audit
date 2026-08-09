let ws = null;
let connected = false;
let agentUrl = "ws://localhost:3000/ext";

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "connect") {
    agentUrl = msg.url || agentUrl;
    connectToAgent();
    sendResponse({ ok: true });
  } else if (msg.type === "disconnect") {
    disconnectFromAgent();
    sendResponse({ ok: true });
  } else if (msg.type === "status") {
    sendResponse({ connected, url: agentUrl });
  } else if (msg.type === "page_data") {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "page_data", data: msg.data }));
    }
    sendResponse({ ok: true });
  }
  return true;
});

function connectToAgent() {
  if (ws) ws.close();

  ws = new WebSocket(agentUrl);

  ws.onopen = () => {
    connected = true;
    broadcast({ type: "agent_connected" });
    ws.send(JSON.stringify({ type: "hello", source: "extension" }));
  };

  ws.onclose = () => {
    connected = false;
    broadcast({ type: "agent_disconnected" });
    setTimeout(() => {
      if (connected === false) connectToAgent();
    }, 5000);
  };

  ws.onerror = () => {
    connected = false;
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "execute") {
        executeOnOutlookTab(msg);
      }
    } catch {}
  };
}

function disconnectFromAgent() {
  if (ws) {
    ws.close();
    ws = null;
  }
  connected = false;
}

async function executeOnOutlookTab(msg) {
  const tabs = await chrome.tabs.query({
    url: [
      "https://outlook.live.com/*",
      "https://outlook.office.com/*",
      "https://outlook.office365.com/*",
    ],
  });

  if (tabs.length === 0) {
    sendToAgent({ type: "error", message: "No Outlook tab found" });
    return;
  }

  const tab = tabs[0];
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: executeAction,
      args: [msg.action, msg.params || {}],
    });
    sendToAgent({
      type: "action_result",
      action: msg.action,
      data: results[0]?.result,
    });
  } catch (err) {
    sendToAgent({ type: "error", message: err.message });
  }
}

function executeAction(action, params) {
  switch (action) {
    case "get_page_text":
      return document.body.innerText.slice(0, 10000);

    case "get_page_info":
      return { url: window.location.href, title: document.title };

    case "get_email_list": {
      const items = document.querySelectorAll('[role="option"], [role="listitem"]');
      const emails = [];
      items.forEach((item, i) => {
        if (i >= (params.maxCount || 15)) return;
        const text = item.innerText || "";
        const lines = text.split("\n").filter((l) => l.trim());
        emails.push({
          id: `email-${i}`,
          from: lines[0] || "Unknown",
          subject: lines[1] || "No subject",
          preview: lines.slice(2, 4).join(" "),
          date: "",
          isRead: !item.querySelector('[class*="unread"]'),
        });
      });
      return emails;
    }

    case "click_element": {
      const el = document.querySelector(params.selector);
      if (el) { el.click(); return { clicked: true }; }
      return { error: "Element not found" };
    }

    case "fill_element": {
      const el = document.querySelector(params.selector);
      if (el) {
        el.focus();
        el.value = params.value || "";
        el.dispatchEvent(new Event("input", { bubbles: true }));
        return { filled: true };
      }
      return { error: "Element not found" };
    }

    case "scroll": {
      const container = document.querySelector('[role="listbox"], [role="list"]') || document.body;
      container.scrollTop += params.direction === "up" ? -500 : 500;
      return { scrolled: true };
    }

    case "screenshot":
      return { note: "Screenshots require CDP or Playwright — use the dashboard instead" };

    default:
      return { error: `Unknown action: ${action}` };
  }
}

function sendToAgent(data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}

function broadcast(msg) {
  chrome.runtime.sendMessage(msg).catch(() => {});
}

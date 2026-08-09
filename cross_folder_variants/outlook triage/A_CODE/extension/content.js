(() => {
  let keepAliveInterval = null;

  function startKeepAlive() {
    if (keepAliveInterval) return;
    keepAliveInterval = setInterval(() => {
      chrome.runtime.sendMessage({
        type: "page_data",
        data: {
          url: window.location.href,
          title: document.title,
          timestamp: Date.now(),
          hasMailList: !!document.querySelector('[role="listbox"], [role="list"]'),
        },
      }).catch(() => {});
    }, 10000);
  }

  function stopKeepAlive() {
    if (keepAliveInterval) {
      clearInterval(keepAliveInterval);
      keepAliveInterval = null;
    }
  }

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === "agent_connected") {
      startKeepAlive();
      console.log("[Outlook Agent] Connected to agent server");
    } else if (msg.type === "agent_disconnected") {
      stopKeepAlive();
      console.log("[Outlook Agent] Disconnected from agent server");
    }
  });

  chrome.runtime.sendMessage({ type: "status" }, (response) => {
    if (response?.connected) {
      startKeepAlive();
      console.log("[Outlook Agent] Extension active and connected");
    }
  });
})();

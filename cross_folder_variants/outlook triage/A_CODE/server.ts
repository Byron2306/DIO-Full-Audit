import "dotenv/config";
import express from "express";
import { createServer as createViteServer } from "vite";
import { WebSocketServer, WebSocket } from "ws";
import http from "http";
import path from "path";
import { fileURLToPath } from "url";
import { OutlookAgent } from "./src/agent/agent.js";
import { loadProfile, saveProfile, loadContacts, loadMemory } from "./src/knowledge/profile.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function startServer() {
  const app = express();
  const PORT = parseInt(process.env.PORT || "3000");
  const HOST = process.env.HOST || "127.0.0.1";

  app.use(express.json({ limit: "10mb" }));

  const server = http.createServer(app);

  const dashboardWss = new WebSocketServer({ noServer: true });
  const extensionWss = new WebSocketServer({ noServer: true });

  server.on("upgrade", (request, socket, head) => {
    const pathname = new URL(request.url!, `http://${request.headers.host}`).pathname;
    if (pathname === "/ws") {
      dashboardWss.handleUpgrade(request, socket, head, (ws) => {
        dashboardWss.emit("connection", ws, request);
      });
    } else if (pathname === "/ext") {
      extensionWss.handleUpgrade(request, socket, head, (ws) => {
        extensionWss.emit("connection", ws, request);
      });
    } else {
      socket.destroy();
    }
  });

  const agent = new OutlookAgent();
  const dashboardClients = new Set<WebSocket>();
  const extensionClients = new Set<WebSocket>();

  function broadcast(type: string, data: any) {
    const msg = JSON.stringify({ type, data, timestamp: Date.now() });
    for (const ws of dashboardClients) {
      if (ws.readyState === WebSocket.OPEN) ws.send(msg);
    }
  }

  agent.on("log", (log) => broadcast("log", log));
  agent.on("state", (state) => broadcast("state", state));

  // --- Dashboard WebSocket ---

  dashboardWss.on("connection", (ws) => {
    dashboardClients.add(ws);
    ws.send(JSON.stringify({ type: "state", data: agent.getState(), timestamp: Date.now() }));
    ws.on("close", () => dashboardClients.delete(ws));
    ws.on("message", async (raw) => {
      try {
        const msg = JSON.parse(raw.toString());
        if (msg.type === "action") {
          const result = await agent.executeAction(msg.action, msg.params);
          ws.send(JSON.stringify({ type: "action_result", action: msg.action, data: result, timestamp: Date.now() }));
        }
      } catch (err: any) {
        ws.send(JSON.stringify({ type: "error", data: err.message, timestamp: Date.now() }));
      }
    });
  });

  // --- Extension WebSocket ---

  extensionWss.on("connection", (ws) => {
    extensionClients.add(ws);
    broadcast("log", {
      timestamp: new Date().toISOString(),
      type: "info",
      message: "Chrome extension connected",
    });

    ws.on("close", () => {
      extensionClients.delete(ws);
      broadcast("log", {
        timestamp: new Date().toISOString(),
        type: "info",
        message: "Chrome extension disconnected",
      });
    });

    ws.on("message", async (raw) => {
      try {
        const msg = JSON.parse(raw.toString());
        if (msg.type === "page_data") {
          broadcast("log", {
            timestamp: new Date().toISOString(),
            type: "info",
            message: `Extension heartbeat: ${msg.data?.url}`,
          });
        } else if (msg.type === "action_result") {
          broadcast("log", {
            timestamp: new Date().toISOString(),
            type: "result",
            message: `Extension result for ${msg.action}`,
            data: msg.data,
          });
        }
      } catch {}
    });
  });

  // --- Browser Connection ---

  app.post("/api/agent/connect-cdp", async (req, res) => {
    const cdpUrl = req.body.cdpUrl || "http://127.0.0.1:9222";
    try {
      await agent.connectCDP(cdpUrl);
      res.json({ success: true, message: `Connected to Chrome at ${cdpUrl}` });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  app.post("/api/agent/diagnose-cdp", async (req, res) => {
    const cdpUrl = req.body.cdpUrl || "http://127.0.0.1:9222";
    try {
      const result = await agent.diagnoseCDP(cdpUrl);
      res.json(result);
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  app.post("/api/agent/start", async (req, res) => {
    try {
      const headless = req.body.headless !== false;
      await agent.start(headless);
      res.json({ success: true, message: `Agent started (${headless ? "headless" : "headed"})` });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  app.post("/api/agent/start-headed", async (_req, res) => {
    try {
      await agent.startHeaded();
      res.json({ success: true, message: "Agent started in headed mode" });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  app.post("/api/agent/switch-headless", async (_req, res) => {
    try {
      await agent.switchToHeadless();
      res.json({ success: true });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  app.post("/api/agent/switch-headed", async (_req, res) => {
    try {
      await agent.switchToHeaded();
      res.json({ success: true });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  // --- Auth ---

  app.post("/api/agent/login", async (req, res) => {
    if (process.env.ALLOW_PASSWORD_LOGIN !== "true") {
      return res.status(403).json({ error: "Password login is disabled. Sign in interactively in headed mode or use Microsoft Graph OAuth." });
    }
    const { email, password, username } = req.body;
    if (!email || !password) return res.status(400).json({ error: "Email and password required" });
    try {
      const success = await agent.login(email, password, username);
      res.json({ success });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  app.post("/api/agent/check-session", async (_req, res) => {
    try {
      const loggedIn = await agent.checkSession();
      res.json({ loggedIn });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  // --- Actions ---

  app.post("/api/agent/action", async (req, res) => {
    const { action, params } = req.body;
    if (!action) return res.status(400).json({ error: "Action required" });
    try {
      const result = await agent.executeAction(action, params);
      res.json({ success: true, result });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  app.post("/api/agent/run", async (req, res) => {
    const { goal } = req.body;
    if (!goal) return res.status(400).json({ error: "Goal required" });
    res.json({ success: true, message: `Started: ${goal}` });
    agent.runAutonomous(goal).catch((err) => broadcast("error", { message: err.message }));
  });

  app.post("/api/agent/stop", async (_req, res) => {
    agent.stop();
    res.json({ success: true });
  });

  app.get("/api/agent/state", (_req, res) => res.json(agent.getState()));

  app.get("/api/agent/screenshot", async (_req, res) => {
    try {
      const buf = await agent.getScreenshot();
      if (buf) res.type("image/jpeg").send(buf);
      else res.status(404).json({ error: "No screenshot" });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  app.post("/api/agent/shutdown", async (_req, res) => {
    await agent.shutdown();
    res.json({ success: true });
  });

  // --- Profile & Knowledge ---

  app.get("/api/profile", async (_req, res) => {
    try { res.json(await loadProfile()); }
    catch (err: any) { res.status(500).json({ error: err.message }); }
  });

  app.post("/api/profile", async (req, res) => {
    try {
      const current = await loadProfile();
      const updated = { ...current, ...req.body };
      await saveProfile(updated);
      res.json(updated);
    } catch (err: any) { res.status(500).json({ error: err.message }); }
  });

  app.get("/api/contacts", async (_req, res) => {
    try { res.json(await loadContacts()); }
    catch (err: any) { res.status(500).json({ error: err.message }); }
  });

  app.get("/api/memory", async (req, res) => {
    try {
      const entries = await loadMemory();
      const limit = parseInt(req.query.limit as string) || 50;
      res.json(entries.slice(-limit));
    } catch (err: any) { res.status(500).json({ error: err.message }); }
  });

  // --- Vite ---

  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    app.use(express.static(path.join(__dirname, "dist")));
    app.get("*", (_req, res) => {
      res.sendFile(path.join(__dirname, "dist", "index.html"));
    });
  }

  server.listen(PORT, HOST, () => {
    console.log(`
┌─────────────────────────────────────────────────┐
│          Outlook Browser Agent                  │
├─────────────────────────────────────────────────┤
│  Dashboard:  http://${HOST}:${PORT}              │
│  WebSocket:  ws://localhost:${PORT}/ws              │
│  Extension:  ws://localhost:${PORT}/ext             │
│  PinchTab:   pinchtab (v0.7.8) available        │
├─────────────────────────────────────────────────┤
│  To connect to your browser:                    │
│  1. Start Chrome with:                          │
│     chrome --remote-debugging-port=9222         │
│  2. Log into Outlook in that Chrome             │
│  3. Click "CDP Connect" in the dashboard        │
│                                                 │
│  Or install the extension from ./extension/     │
└─────────────────────────────────────────────────┘
`);
  });
}

startServer();

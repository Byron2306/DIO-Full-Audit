import { ChildProcess, spawn } from "child_process";
import { EventEmitter } from "events";

const DEFAULT_PORT = 9867;

/**
 * Wrapper around the PinchTab Go binary.
 * Starts pinchtab as a subprocess and exposes its HTTP API for other agents.
 *
 * PinchTab provides:
 * - Accessibility-tree snapshots (token-efficient, ~1-3K vs 10K+ for screenshots)
 * - Direct actions: click, type, fill, press, scroll, hover, select
 * - Multi-tab management
 * - Stealth mode to bypass bot detection
 * - Session persistence with cookie/auth preservation
 */
export class PinchTabManager extends EventEmitter {
  private process: ChildProcess | null = null;
  private port: number;
  private _running = false;

  constructor(port = DEFAULT_PORT) {
    super();
    this.port = port;
  }

  get baseUrl(): string {
    return `http://127.0.0.1:${this.port}`;
  }

  get running(): boolean {
    return this._running;
  }

  async start(stealth = true): Promise<boolean> {
    if (this._running) return true;

    const args = ["--port", String(this.port)];
    if (stealth) args.push("--stealth");

    return new Promise((resolve) => {
      this.process = spawn("pinchtab", args, {
        stdio: ["ignore", "pipe", "pipe"],
      });

      let started = false;

      this.process.stdout?.on("data", (data: Buffer) => {
        const msg = data.toString();
        this.emit("log", msg);
        if (!started && (msg.includes("listening") || msg.includes("ready") || msg.includes("started"))) {
          started = true;
          this._running = true;
          resolve(true);
        }
      });

      this.process.stderr?.on("data", (data: Buffer) => {
        this.emit("error", data.toString());
      });

      this.process.on("exit", (code) => {
        this._running = false;
        this.process = null;
        this.emit("exit", code);
      });

      setTimeout(() => {
        if (!started) {
          this._running = true;
          resolve(true);
        }
      }, 3000);
    });
  }

  async stop(): Promise<void> {
    if (this.process) {
      this.process.kill("SIGTERM");
      this.process = null;
    }
    this._running = false;
  }

  private async request(method: string, path: string, body?: any): Promise<any> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) throw new Error(`PinchTab ${method} ${path}: ${res.status}`);
    const text = await res.text();
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  }

  async startBrowser(options?: { headless?: boolean; stealth?: boolean }): Promise<any> {
    return this.request("POST", "/browser/start", options);
  }

  async navigate(url: string): Promise<any> {
    return this.request("POST", "/navigate", { url });
  }

  async snapshot(): Promise<any> {
    return this.request("GET", "/snapshot");
  }

  async click(elementRef: string): Promise<any> {
    return this.request("POST", "/action", { action: "click", ref: elementRef });
  }

  async type(elementRef: string, text: string): Promise<any> {
    return this.request("POST", "/action", { action: "type", ref: elementRef, text });
  }

  async fill(elementRef: string, value: string): Promise<any> {
    return this.request("POST", "/action", { action: "fill", ref: elementRef, value });
  }

  async press(key: string): Promise<any> {
    return this.request("POST", "/action", { action: "press", key });
  }

  async scroll(direction: "up" | "down", amount?: number): Promise<any> {
    return this.request("POST", "/action", { action: "scroll", direction, amount });
  }

  async extractText(mode: "readability" | "raw" = "readability"): Promise<any> {
    return this.request("GET", `/text?mode=${mode}`);
  }

  async screenshot(): Promise<Buffer> {
    const res = await fetch(`${this.baseUrl}/screenshot`);
    return Buffer.from(await res.arrayBuffer());
  }

  async evaluate(js: string): Promise<any> {
    return this.request("POST", "/evaluate", { expression: js });
  }

  async getTabs(): Promise<any> {
    return this.request("GET", "/tabs");
  }

  async newTab(url?: string): Promise<any> {
    return this.request("POST", "/tabs/new", url ? { url } : undefined);
  }

  async switchTab(index: number): Promise<any> {
    return this.request("POST", `/tabs/${index}/activate`);
  }
}

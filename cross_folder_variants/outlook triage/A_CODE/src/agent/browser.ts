import { chromium, Browser, BrowserContext, Page } from "playwright";
import path from "path";
import fs from "fs/promises";
import { EventEmitter } from "events";

const USER_DATA_DIR = path.resolve("browser-profile");
const SESSION_DIR = path.resolve("playwright-session");

export type ConnectionMode = "cdp" | "standalone" | "extension";

export interface ConnectionInfo {
  mode: ConnectionMode;
  cdpUrl?: string;
  extensionPort?: number;
}

/**
 * Three connection modes:
 *
 * 1. CDP ("Connect to My Browser") — The recommended way.
 *    User starts their Chrome with --remote-debugging-port=9222,
 *    logs into Outlook normally, and we connect to their live session.
 *    Zero detection risk because it IS their real browser.
 *    Session persists as long as Chrome is running.
 *
 * 2. Standalone — Launches a new Chromium instance (headless or headed).
 *    Uses persistent profile dir + stealth scripts.
 *    Requires a display for headed mode.
 *
 * 3. Extension — The agent serves a WebSocket that a Chrome extension
 *    connects to. The extension injects content scripts into Outlook
 *    and relays actions. (Handled separately via the extension relay.)
 */
export class BrowserManager extends EventEmitter {
  private browser: Browser | null = null;
  private context: BrowserContext | null = null;
  private _page: Page | null = null;
  private _isRunning = false;
  private _mode: ConnectionMode = "standalone";

  get page(): Page | null {
    return this._page;
  }

  get isRunning(): boolean {
    return this._isRunning;
  }

  get mode(): ConnectionMode {
    return this._mode;
  }

  private stealthScripts(): string {
    return `
      Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

      if (!window.navigator.chrome) {
        window.navigator.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {} };
      }

      const originalQuery = window.navigator.permissions.query;
      window.navigator.permissions.query = (parameters) =>
        parameters.name === 'notifications'
          ? Promise.resolve({ state: Notification.permission })
          : originalQuery(parameters);

      Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5].map(() => ({
          name: 'Chrome PDF Plugin',
          description: 'Portable Document Format',
          filename: 'internal-pdf-viewer',
          length: 1,
        })),
      });

      Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en'],
      });

      const getParameter = WebGLRenderingContext.prototype.getParameter;
      WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter.call(this, parameter);
      };
    `;
  }

  /**
   * Connect to the user's already-running Chrome via CDP.
   * This is the primary recommended method.
   *
   * The user launches Chrome with:
   *   chrome --remote-debugging-port=9222
   *
   * Or on macOS:
   *   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
   *
   * Or on Windows:
   *   chrome.exe --remote-debugging-port=9222
   *
   * Then logs into Outlook in that Chrome. We connect and control it.
   */
  async connectCDP(cdpUrl = "http://127.0.0.1:9222"): Promise<Page> {
    if (this._page && this._isRunning) {
      return this._page;
    }

    this._mode = "cdp";

    const normalizedUrl = cdpUrl.replace("localhost", "127.0.0.1");

    const reachable = await this.checkCDPReachable(normalizedUrl);
    if (!reachable) {
      throw new Error(
        `Cannot reach Chrome at ${normalizedUrl}. ` +
        `Make sure Chrome is running with --remote-debugging-port=9222. ` +
        `Important: close ALL Chrome windows first, then reopen with the flag. ` +
        `If Chrome was already running, it silently ignores the flag.`
      );
    }

    this.emit("status", { type: "browser", status: "connecting_cdp" });

    this.browser = await chromium.connectOverCDP(normalizedUrl);

    const contexts = this.browser.contexts();
    if (contexts.length === 0) {
      throw new Error("No browser contexts found. Is Chrome running with --remote-debugging-port?");
    }

    this.context = contexts[0];
    const pages = this.context.pages();

    let outlookPage = pages.find(
      (p) =>
        p.url().includes("outlook.live.com") ||
        p.url().includes("outlook.office.com") ||
        p.url().includes("outlook.office365.com")
    );

    if (!outlookPage && pages.length > 0) {
      outlookPage = pages[0];
    }

    if (!outlookPage) {
      outlookPage = await this.context.newPage();
    }

    this._page = outlookPage;
    this._isRunning = true;

    this._page.on("close", () => {
      if (this.context && this.context.pages().length === 0) {
        this._isRunning = false;
        this.emit("status", { type: "browser", status: "page_closed" });
      }
    });

    const url = this._page.url();
    const title = await this._page.title();
    this.emit("status", {
      type: "browser",
      status: `connected_cdp`,
      detail: `Connected to ${title} (${url})`,
    });

    return this._page;
  }

  async launch(headless = true): Promise<Page> {
    if (this._page && this._isRunning) {
      return this._page;
    }

    this._mode = "standalone";
    await fs.mkdir(USER_DATA_DIR, { recursive: true });
    await fs.mkdir(SESSION_DIR, { recursive: true });

    this.emit("status", {
      type: "browser",
      status: headless ? "launching_headless" : "launching_headed",
    });

    this.context = await chromium.launchPersistentContext(USER_DATA_DIR, {
      headless,
      args: [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-infobars",
        "--window-size=1440,900",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-default-apps",
      ],
      viewport: { width: 1440, height: 900 },
      userAgent:
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
      locale: "en-US",
      timezoneId: "Africa/Johannesburg",
      ignoreHTTPSErrors: true,
      bypassCSP: true,
    });

    await this.context.addInitScript(this.stealthScripts());

    const pages = this.context.pages();
    this._page = pages.length > 0 ? pages[0] : await this.context.newPage();
    this._isRunning = true;

    this._page.on("close", () => {
      if (this.context && this.context.pages().length === 0) {
        this._isRunning = false;
        this.emit("status", { type: "browser", status: "page_closed" });
      }
    });

    this.emit("status", { type: "browser", status: "launched" });
    return this._page;
  }

  async relaunchHeaded(): Promise<Page> {
    await this.close();
    return this.launch(false);
  }

  async relaunchHeadless(): Promise<Page> {
    await this.close();
    return this.launch(true);
  }

  async saveSessionBackup(): Promise<void> {
    if (this._mode === "cdp") return;
    try {
      const state = await this.context?.storageState();
      if (state) {
        await fs.mkdir(SESSION_DIR, { recursive: true });
        await fs.writeFile(
          path.join(SESSION_DIR, "state-backup.json"),
          JSON.stringify(state, null, 2)
        );
      }
      this.emit("status", { type: "browser", status: "session_backed_up" });
    } catch (err) {
      console.error("Failed to backup session:", err);
    }
  }

  async screenshot(): Promise<Buffer | null> {
    if (!this._page) return null;
    return (await this._page.screenshot({ type: "jpeg", quality: 60 })) as Buffer;
  }

  async getPageText(): Promise<string> {
    if (!this._page) return "";
    return await this._page.innerText("body").catch(() => "");
  }

  async getAccessibilityTree(): Promise<string> {
    if (!this._page) return "";
    try {
      return await this._page.locator("body").ariaSnapshot();
    } catch {
      return await this.getPageText();
    }
  }

  async findOutlookTab(): Promise<boolean> {
    if (!this.context) return false;
    const pages = this.context.pages();
    const outlookPage = pages.find(
      (p) =>
        p.url().includes("outlook.live.com") ||
        p.url().includes("outlook.office.com") ||
        p.url().includes("outlook.office365.com")
    );
    if (outlookPage) {
      this._page = outlookPage;
      this.emit("status", { type: "browser", status: "switched_to_outlook_tab" });
      return true;
    }
    return false;
  }

  async listTabs(): Promise<{ index: number; url: string; title: string }[]> {
    if (!this.context) return [];
    const pages = this.context.pages();
    const tabs = [];
    for (let i = 0; i < pages.length; i++) {
      tabs.push({
        index: i,
        url: pages[i].url(),
        title: await pages[i].title().catch(() => ""),
      });
    }
    return tabs;
  }

  async switchToTab(index: number): Promise<boolean> {
    if (!this.context) return false;
    const pages = this.context.pages();
    if (index >= 0 && index < pages.length) {
      this._page = pages[index];
      await this._page.bringToFront();
      return true;
    }
    return false;
  }

  private async checkCDPReachable(url: string): Promise<boolean> {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 3000);
      const res = await fetch(`${url}/json/version`, { signal: controller.signal });
      clearTimeout(timeout);
      return res.ok;
    } catch {
      return false;
    }
  }

  async diagnoseCDP(url = "http://127.0.0.1:9222"): Promise<{
    reachable: boolean;
    version?: any;
    tabs?: any[];
    error?: string;
    tips: string[];
  }> {
    const tips: string[] = [];
    const normalizedUrl = url.replace("localhost", "127.0.0.1");

    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 3000);
      const versionRes = await fetch(`${normalizedUrl}/json/version`, { signal: controller.signal });
      clearTimeout(timeout);

      if (!versionRes.ok) {
        tips.push("Chrome is responding but returned an error. Try restarting Chrome.");
        return { reachable: false, tips, error: `HTTP ${versionRes.status}` };
      }

      const version = await versionRes.json();

      const tabsRes = await fetch(`${normalizedUrl}/json/list`);
      const tabs = await tabsRes.json();

      const outlookTabs = tabs.filter((t: any) =>
        t.url?.includes("outlook.live.com") ||
        t.url?.includes("outlook.office.com") ||
        t.url?.includes("outlook.office365.com")
      );

      if (outlookTabs.length === 0) {
        tips.push("Chrome is connected but no Outlook tab found. Open outlook.live.com in that Chrome window.");
      }

      return {
        reachable: true,
        version: { browser: version.Browser, v8: version["V8-Version"] },
        tabs: tabs.map((t: any) => ({ title: t.title, url: t.url })),
        tips,
      };
    } catch (err: any) {
      tips.push("Chrome is not reachable on port 9222.");
      tips.push("Make sure to CLOSE ALL Chrome windows first, then reopen with:");
      tips.push("  chrome --remote-debugging-port=9222");
      tips.push("If Chrome was already running when you added the flag, it silently ignores it.");
      tips.push("On macOS: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222");
      tips.push("On Windows: chrome.exe --remote-debugging-port=9222");
      return { reachable: false, error: err.message, tips };
    }
  }

  async close(): Promise<void> {
    await this.saveSessionBackup();
    if (this._mode === "cdp") {
      if (this.browser) await this.browser.close().catch(() => {});
    } else {
      if (this.context) await this.context.close().catch(() => {});
    }
    this._page = null;
    this.context = null;
    this.browser = null;
    this._isRunning = false;
    this.emit("status", { type: "browser", status: "closed" });
  }

  async disconnect(): Promise<void> {
    this._page = null;
    this.context = null;
    if (this.browser) await this.browser.close().catch(() => {});
    this.browser = null;
    this._isRunning = false;
    this.emit("status", { type: "browser", status: "disconnected" });
  }
}

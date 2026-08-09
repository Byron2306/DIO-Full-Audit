# AGENTS.md

## Cursor Cloud specific instructions

### Overview

This is the **Outlook Browser Agent** — a Playwright-based browser automation tool with a React dashboard. It controls Outlook through real browser automation (no OAuth/Graph API). See `README.md` for full architecture and feature details.

### Services

| Service | Command | Port | Notes |
|---------|---------|------|-------|
| Dev server (Express + Vite) | `npm run dev` | 3000 | Single process: Express backend + Vite SPA middleware |

### Key commands

- **Install deps:** `npm install`
- **Install browsers:** `npm run install-browsers` (installs Playwright Chromium)
- **Lint:** `npm run lint` (runs `tsc --noEmit`)
- **Build:** `npm run build` (Vite production build)
- **Dev server:** `npm run dev` (runs `tsx server.ts`)

### Gotchas

- Playwright requires system-level dependencies for Chromium. If `npm run install-browsers` succeeds but Chromium won't launch, run `npx playwright install-deps chromium` (needs root).
- The dev server loads env vars from `.env.local` via `dotenv/config`. The only env var needed for basic operation is `GEMINI_API_KEY` (for AI features). Without it, the dashboard and non-AI actions still work.
- Agent data (profile, contacts, memory) persists to the `agent-data/` directory and browser profile persists to `browser-profile/`. Both are gitignored.
- The WebSocket endpoint is at `/ws` (dashboard) and `/ext` (Chrome extension). The dashboard auto-reconnects on WS disconnect.
- Browser automation features (CDP connect, standalone launch) require Chromium to be installed via `npm run install-browsers`.

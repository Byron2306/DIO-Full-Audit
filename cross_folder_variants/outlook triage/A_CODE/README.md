# Outlook Browser Agent

A personal AI agent that controls Outlook through **real browser automation** (Playwright) — no OAuth app registration, no Microsoft Graph API, no client secrets. It logs into Outlook the same way you do: through the browser.

This isn't just an email automator. It **understands who you are**, knows your work context, fetches research papers, builds memory from past interactions, and can even fill out basic documents.

## How It Gets Past OAuth

Microsoft blocks most Playwright scripts because they detect automation signals (`navigator.webdriver`, missing browser plugins, headless fingerprints, etc.). This project handles that through:

1. **Persistent browser profile** (`launchPersistentContext`) — maintains a real Chrome user data directory with all cookies, localStorage, IndexedDB, and service workers. This is fundamentally different from `storageState` which only saves cookies.

2. **Stealth injection** — strips `navigator.webdriver`, fakes Chrome plugin objects, spoofs WebGL vendor strings, and patches the permissions API. Microsoft's login page sees a normal browser.

3. **Headed first login** — the first time, you launch in **headed mode** (visible browser window). You log in manually, handle any 2FA/CAPTCHA yourself. The session gets persisted to disk. After that, headless works.

4. **Human-like interaction** — typing delays, natural wait times, and real DOM events instead of direct API calls.

**The key insight**: once you've logged in once with a real browser profile and saved it, subsequent launches (even headless) carry the full authentication state. This is how OpenClaw's "clippy" skill works too.

## Architecture

```
┌──────────────────────────────────────────────────┐
│              Web Dashboard (React)               │
│  Profile · Login · Agent · Research · Memory     │
└─────────────────┬────────────────────────────────┘
                  │ REST + WebSocket
┌─────────────────┴────────────────────────────────┐
│              Express Server                      │
│  Agent API · Profile API · Screenshot · WS       │
└─────────────────┬────────────────────────────────┘
                  │
┌─────────────────┴────────────────────────────────┐
│           Outlook Agent (Agentic Loop)           │
│  Gemini AI observes → decides → executes →       │
│  remembers → repeats                             │
├──────────────────────────────────────────────────┤
│  Knowledge Layer                                 │
│  Profile · Contacts · Memory · Research Papers   │
└─────────────────┬────────────────────────────────┘
                  │
┌─────────────────┴────────────────────────────────┐
│   Playwright (Persistent Chromium Profile)       │
│   + PinchTab (accessibility-tree snapshots)      │
│   outlook.live.com / outlook.office.com          │
└──────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Install dependencies
npm install

# 2. Install browsers
npm run install-browsers

# 3. Set your Gemini API key (optional but recommended)
cp env.example .env
# Edit .env and add GEMINI_API_KEY

# 4. Start the server
npm run dev
```

Open `http://localhost:3000` and:
1. Click **Headed** to launch a visible browser
2. Click **Auto Login** or navigate manually to log into Outlook
3. Once logged in, click **Hide Browser** to switch to headless
4. The session persists across restarts

## Features

### Personal Context (Profile Tab)
The agent knows you:
- **Who you are**: name, role, organization, department
- **What you do**: expertise, current projects, bio
- **How you communicate**: preferred tone, sign-off style
- **Your inbox structure**: custom folder names

Every AI operation uses this context — classification considers your work, drafts match your voice, summaries prioritize what matters to you.

### Situational Awareness (Memory Tab)
The agent remembers:
- Emails it has read and their context
- Decisions it has made
- Research it has done
- Contacts it has learned about

Memory persists across sessions and is used to provide context for future interactions. When you get a follow-up email, the agent connects it to previous threads.

### Research Papers
Search Semantic Scholar directly from the dashboard:
- Find papers by topic, author, or keyword
- View abstracts, citation counts, venues
- Access open-access PDFs
- The autonomous agent can search papers as part of a goal

### Document Filling
The agent can analyze forms and documents visible in the browser and suggest field values based on your profile. It uses your stored personal information to auto-fill name, email, student number, department, etc.

### Autonomous Agent
Natural language goals that leverage all capabilities:
- *"Read my unread emails, classify them by priority, and summarize what I need to do today"*
- *"Find the email from Dr. Smith about the extension deadline and draft a reply"*
- *"Search for papers on transformer architectures and save the key findings"*
- *"Go to the registration form and fill it out with my details"*

### Manual Control
Full set of quick actions for direct control:
- Get/read/compose/reply-draft emails. Final sending is reserved for the DIO Control Deck's exact-draft Microsoft Graph transport.
- Navigate folders, scroll, search
- Classify, draft, analyze context
- Screenshot, page text, form filling

## PinchTab Integration

[PinchTab](https://pinchtab.com) (v0.7.8) is installed globally and available as a standalone tool for other agents. It provides:
- **Accessibility-tree snapshots** (~1-3K tokens vs 10K+ for screenshots)
- **Direct browser actions** via HTTP API (click, type, fill, scroll)
- **Multi-tab management** with session persistence
- **Stealth mode** to bypass bot detection

```bash
# Start PinchTab server (for other agents)
pinchtab --stealth --port 9867

# Use via HTTP API
curl http://localhost:9867/snapshot
curl -X POST http://localhost:9867/navigate -d '{"url":"https://outlook.live.com"}'
```

A TypeScript wrapper is available at `src/agent/pinchtab.ts` for programmatic use.

## Project Structure

```
src/
├── agent/
│   ├── browser.ts     # Playwright: persistent context, stealth, headed/headless
│   ├── outlook.ts     # Outlook selectors and browser automation actions
│   ├── agent.ts       # Agentic orchestrator with 20+ actions
│   └── pinchtab.ts    # PinchTab HTTP API wrapper
├── ai/
│   └── gemini.ts      # Context-aware AI: classify, draft, analyze, decide
├── knowledge/
│   ├── profile.ts     # User profile, contacts, persistent memory
│   └── research.ts    # Semantic Scholar API, web presence scouting
├── App.tsx            # React dashboard (6 tabs)
├── main.tsx           # Entry point
└── index.css          # Tailwind styles

server.ts              # Express + WebSocket server
agent-data/            # Persisted profile, contacts, memory (gitignored)
browser-profile/       # Chromium user data directory (gitignored)
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | For AI features | [Get one free](https://aistudio.google.com/apikey) |
| `PORT` | No | Server port (default: 3000) |

## How This Compares

| Feature | This Project | PinchTab | OpenClaw Clippy |
|---------|-------------|----------|-----------------|
| OAuth needed | No | No | No |
| Browser automation | Playwright | Go + Chrome DevTools | Playwright |
| AI integration | Gemini (built-in) | External | External |
| Personal context | Full profile + memory | None | None |
| Research papers | Semantic Scholar API | None | None |
| Document filling | Yes | Manual | No |
| Web dashboard | Yes | CLI only | No |
| Session persistence | Full Chrome profile | Cookies | Cookies |

## License

MIT

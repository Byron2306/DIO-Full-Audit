# AI → Triune Integration Map

This document maps the AI capabilities in the codebase (including existing Ollama integration) into the Triune architecture (Metatron, Michael, Loki). It provides recommended data flows, API touchpoints, and UI contract examples.

## Summary
- Local LLM: Ollama (containerized, configured via `/api/advanced/ai/ollama/*`).
- Lightweight reasoner shim: `backend/ai/reasoner.py` (heuristic fallback + OpenAI support if keys present).
- Michael uses `backend/triune/michael.py` for ranking; that implementation now optionally calls `explain_candidates`.
- Metatron exposes `GET /api/metatron/state` containing `triune_analyses` and per-candidate `components` including AI `provider` and `explanation`.

## Where AI is used
- Metatron
  - Uses graph analytics, sequence models, and optionally LLMs for narrative synthesis.
  - UI: `GET /api/metatron/state` includes `hypotheses` and `triune_analyses` with AI explanations.

- Michael
  - Core: deterministic ranking + light ML heuristics in `backend/triune/michael.py`.
  - AI: tries to call `backend.ai.reasoner.explain_candidates` to attach per-candidate explanations.
  - Persistence: `backend/tasks/triune_tasks.michael_analyze` saves `ranked` results to `db.triune_analysis`.

- Loki
  - Primarily heuristic and synthetic hypothesis generation; LLMs may be used in future to propose novel hunt ideas (use sandboxed calls only).

## Ollama integration
- Existing endpoints and UI configuration live under the Advanced Services page (frontend: `frontend/src/pages/AdvancedServicesPage.jsx`).
- Ollama configuration endpoints:
  - `POST /api/advanced/ai/ollama/configure` — configure base URL and model.
  - `GET /api/advanced/ai/ollama/status` — check connectivity.
- When Ollama is configured, `backend/ai/reasoner.py` can be extended to call Ollama's HTTP API (the current shim tries OpenAI first; extend to use Ollama `POST /v1/complete` or similar).

## Data flow recommendations
1. Observation → World Model (events ingested by Loki endpoints and `WorldModelService`).
2. Periodic/On-demand Michael analysis (`michael_analyze`) collects candidate responses and ranks them.
3. Michael writes `triune_analysis` records to database including `ranked` array (each entry may include `components` and `ai` explanation).
4. Metatron aggregates analyses, builds narrative, and exposes `GET /api/metatron/state` for UI.
5. UI displays `components` breakdown and `ai` explanation (provider + text) for human review.

## UI contract / schema
- `triune_analyses[].ranked[]` objects include:
  - `candidate`: string
  - `score`: float (0..1)
  - `components`: object with keys `keyword`, `risk`, `recency`, `degree`, and optional `ai` which is `{ provider: string, explanation: string, score_delta?: float }`

- Example file: `backend/schemas/triune_ui_example.json` (copy into frontend to mock data during UI development).

## Security and Governance
- Ollama runs local models; treat any LLM output as advisory only.
- LLM outputs must be persisted with provenance: provider, model, prompt, timestamp, and request id.
- Never allow LLM outputs to execute actions. Use Michael's policy gates and approval workflows for any automated action.

## Next integration tasks (suggested)
1. Implement `backend/ai/ollama_client.py` that wraps Ollama HTTP API and returns structured explanations.
2. Extend `backend/ai/reasoner.py` to prefer Ollama when configured (followed by OpenAI if configured, then heuristics).
3. Log LLM requests/responses to `db.ai_requests` with metadata for auditing and retraining.
4. Add frontend components to render `components` (bar chart) and `ai.explanation` (collapsible text with provider badge).

## Quick dev steps
- To mock UI without Ollama, use `backend/schemas/triune_ui_example.json` in the frontend.
- To enable Ollama locally, run the included Docker Compose service `ollama` and configure the Advanced Services page with `http://host.docker.internal:11434`.

----

This map should help the frontend and backend teams converge on a single contract for AI outputs and ensure AI is advisory and auditable within the Triune architecture.

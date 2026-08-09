# Outlook Triage Adapter

Purpose:

```text
Convert KnowEdge Outlook Triage CSV/JSON outputs into AutoRelease job envelopes.
```

Phase 1 input options:

- Demo inbox JSON.
- `triage_summary.csv` from KnowEdge Outlook Triage.
- Future: selected approved messages from the Outlook Triage dashboard.

Output:

- One job JSON file per routed message.
- A `run_summary.json` file.

Current command:

```bash
python scripts/route_intake.py --input samples/inbox/demo_inbox.json --out runs/latest
```

Commercial posture:

- Draft-only.
- No automatic sending.
- Human approval required before any product route runs.


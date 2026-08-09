# Evidex Adapter

Purpose:

```text
Accept AutoRelease jobs routed to Evidex and prepare evidence-pack requests.
```

Phase 1 should create:

- Evidence manifest.
- Source list.
- KPI/proof/source skeleton.
- Delivery pack folder.
- Review checklist.

Existing project:

```text
/home/byron/Evidex
```

Current command:

```bash
python3 scripts/run_evidex_jobs.py --run runs/latest --out deliverables/latest
```

This creates an Evidex-compatible intake folder and calls:

```bash
/home/byron/Evidex/.venv/bin/python -m evidence_pack_engine.cli generate
```

The Phase 1 runner disables LLM usage so the deterministic pack path is proven first.

Near-term build:

1. Read `runs/latest/evidex/*.json`.
2. Create `deliverables/evidex/<job_id>/`.
3. Write `EVIDENCE_MANIFEST.md`.
4. Write `CLIENT_REVIEW_CHECKLIST.md`.
5. Later call the Evidex pack engine.

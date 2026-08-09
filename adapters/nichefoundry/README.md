# NicheFoundry Adapter

Purpose:

```text
Accept AutoRelease jobs routed to NicheFoundry and prepare campaign/content pack requests.
```

Phase 1 should create:

- Campaign brief.
- Audience hypothesis.
- Offer angle.
- Content checklist.
- Human editorial approval gate.

Existing project:

```text
/home/byron/Downloads/NicheFoundry_Phase11
```

Current command:

```bash
python3 scripts/run_nichefoundry_jobs.py --run runs/latest --out deliverables/latest
```

This creates:

- `foundry_opportunity.json`
- `foundry_campaign_request.json`
- `CAMPAIGN_PACK.md`
- `NICHEFOUNDRY_RUN_RECEIPT.json`

Near-term build:

1. Read `runs/latest/nichefoundry/*.json`.
2. Create `deliverables/nichefoundry/<job_id>/`.
3. Write campaign pack outputs.
4. Validate against NicheFoundry opportunity/story conventions.
5. Later call the NicheFoundry production pipeline.

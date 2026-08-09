# HOMS Adapter

Purpose:

```text
Accept AutoRelease jobs routed to HOMS and prepare marking-batch requests.
```

Current command:

```bash
python3 scripts/run_homs_jobs.py --run runs/latest --out deliverables/latest
```

This creates:

- `homs_marking_request.json`
- `HOMS_MARKING_REQUEST.md`
- `HOMS_RUN_RECEIPT.json`

The Phase 1 adapter does not start the HOMS backend or run AI marking.

Required HOMS inputs:

- Assignment batch ZIP or folder.
- Rubric, memo, essay matrix, or marking guide.
- Optional gradebook CSV.
- Optional assignment instructions.

Approval posture:

```text
AI prepares marking support. Educator approves final marks and feedback.
```


# Evidex Adapter

Purpose:

```text
Accept AutoRelease jobs routed to Evidex and prepare evidence-pack requests.
```

The embedded Evidex engine owns:

- Source ingestion and copied-source custody.
- Claim classification and source binding.
- Evidence tables, narrative drafts, invoice drafts, and the review gate.
- `SOURCE_REVIEW.json`, where `human_review_required` and `release_authorized` are authoritative.

After the engine succeeds, DIO's shared product systems finish the pack:

- **Format Core** renders DOCX and HTML customer-review candidates under `05_STUDIO_FINISH/FORMAT_CORE/` with the `dio_professional` and `editable_review` profiles.
- **Production Studio** records the packaged customer-review boundary in `05_STUDIO_FINISH/EVIDEX_STUDIO_FINISH_RECEIPT.json` and reseals the ZIP atomically.
- **NicheFoundry** remains available for an approved brand-material request. It does not add imagery or marketing claims to audit packs by default.

All shared finishing runs in review mode. External delivery, publication, spend, and authority remain refused, and an unverified Evidex claim remains visibly `UNVERIFIED` in the formatted review artifact.

Existing project:

```text
/home/byron/Evidex
```

Current command:

```bash
python3 scripts/run_evidex_jobs.py --run runs/latest --out deliverables/latest
```

This creates an Evidex-compatible intake folder, calls:

```bash
/home/byron/Evidex/.venv/bin/python -m evidence_pack_engine.cli generate
```

and then invokes `products.evidex_studio_finish.finish_evidex_archive`. The runner disables LLM usage so the deterministic pack path is proven first.

If engine generation succeeds but shared finishing fails, `EVIDEX_RUN_RECEIPT.json` records:

```json
{
  "engine_returncode": 0,
  "returncode": 1,
  "studio_finish": {
    "status": "failed"
  }
}
```

The generated pack directory and original ZIP remain on disk for diagnosis. A successful run replaces the ZIP only after a complete sibling archive has been written.

Operator review:

1. Open `SOURCE_REVIEW.json` and resolve every human-review item.
2. Inspect the Format Core HTML or DOCX review candidate.
3. Confirm payment configuration before using the invoice or delivery email.
4. Record separate authorization before external delivery; pack generation does not grant it.

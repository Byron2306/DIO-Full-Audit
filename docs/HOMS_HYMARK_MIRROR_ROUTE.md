# HOMS HyMark Mirror Route

This route keeps KnowEdge responsible for intake and delivery orchestration, while the actual marking logic comes from the existing HyMark Smart Assessor in:

`/home/byron/Downloads/NoEdge-Multi-Hymark-main/backend/server.py`

## Flow

1. Outlook receives a HOMS marking request.
2. Client uploads batch files into the OneDrive/local mirror job folder.
3. The local job folder contains:
   - `intake.json`
   - `rubric.json`
   - optional `memo.md`
   - `gradebook.csv`
   - `uploads/*`
4. KnowEdge runs the HyMark bridge:

```bash
python3 scripts/run_homs_hymark_batch.py \
  --provider nim \
  --secret-file /home/byron/EdgeK-BEAST/.beast/provider_secrets.env \
  --input /home/byron/KnowEdge_Microsoft_Mirror/HOMS/incoming/HOMS-HUMAN-DUMMY-001_EDU221-short-essay \
  --out /home/byron/KnowEdge_Microsoft_Mirror/HOMS/done
```

5. HyMark performs rubric-driven assessment with criterion feedback, score validation, strengths, improvement areas, and annotations.
6. Outputs are written to `HOMS/done/<job_id>/`:
   - `results.json`
   - `marks.csv`
   - `gradebook_marked.csv`
   - `LECTURER_REVIEW_SUMMARY.md`
   - `feedback/*_FEEDBACK.txt`
   - `HOMS_HYMARK_REVIEW_PACK.zip`
   - `HOMS_HYMARK_BATCH_RECEIPT.json`

## Current Proof

Authoritative proof artifacts are stored at:

`campaigns/phase3/homs/human_dummy_batch/proof/`

The older placeholder runner artifacts have been moved to:

`campaigns/phase3/homs/human_dummy_batch/proof/legacy_placeholder/`

## Provider

The bridge uses NVIDIA NIM through HyMark's OpenAI-compatible client:

- `OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1`
- `HOMS_AI_MODEL=nvidia/nemotron-3-super-120b-a12b`
- key source: `/home/byron/EdgeK-BEAST/.beast/provider_secrets.env`

Secrets are never written to proof artifacts; receipts record only secret variable names.

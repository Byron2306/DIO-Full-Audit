# Sophia Academic Review Adapter

Purpose:

```text
Academic manuscript + research question
-> governed literature discovery
-> technical citation/reference audit
-> claim/source support map
-> Sophia reviewer commentary
-> human approval pack
```

Run a request while Sophia Presence is available locally at `127.0.0.1:7070`:

```bash
python3 scripts/run_sophia_review.py samples/sophia/demo_request.json
```

The manuscript is not copied into the delivery pack. Only explicitly approved search queries are sent to scholarly indexes. Gemini reviewer commentary is disabled unless the request contains `"gemini_review_approved": true`; when approved, up to 180,000 extracted manuscript characters are transmitted to Gemini through Sophia's reasoned integrity lane. The receipt records the provider, model, transmitted character count, Mandos result, article-conformity result, and grounding validation.

Gemini commentary is released only when the response came from the Gemini reasoned lane, passed Mandos and Genesis checks, cited valid paragraph/claim anchors, and introduced no unknown citations or DOIs. Candidate abstracts, metadata, citation strings, and support labels remain verification leads until a human checks the full source.

Final delivery is always blocked pending human approval.

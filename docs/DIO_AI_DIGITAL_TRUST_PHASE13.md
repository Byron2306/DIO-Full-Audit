# DIO Phase 13 — AI & Digital Trust

Phase 13 makes AI trust inspectable, evidence-bound and deterministic. It does not ask whether an AI system sounds convincing. It binds identity, provenance, evaluation, authority, tool safety, data boundaries, integrity, drift and release state into a canonical AI Trust Envelope.

## Canonical trust dimensions

- **identity** — exact system, model, provider and version identity
- **provenance** — source, prompt, attachment and output lineage
- **evaluation** — purpose-bound evaluation evidence
- **freshness** — whether evaluation applies to the current version and time
- **authority** — explicit human or policy authority for consequential decisions
- **tool_safety** — declared tools, targets and permitted effects
- **data_boundary** — handling, retention and disclosure constraints
- **integrity** — canonical fingerprints and tamper detection
- **drift** — model, prompt, policy, connector or environment change
- **release** — explicit external-release decision

States remain independent: `SUPPORTED`, `PARTIAL`, `UNKNOWN`, `CONTESTED`, `STALE`, `REFUSE`, and `NEEDS_YOU`.

## Reference incarnations

### DIO AITrustProof

Produces a human-readable AI Trust Dossier covering identity, intended use, evidence, evaluations, unresolved gaps, prohibited claims and human decisions.

### DIO AgentAuthority

Examines an agent's requested tools, targets, permissions and effects. Untrusted content cannot grant authority. External effects require an explicit capability and human authority receipt.

### DIO ModelChangeProof

Compares baseline and current model, prompt, policy, connector and environment fingerprints. Changed components make inherited evaluations stale until bounded re-evaluation occurs.

## Adversarial reference

The Phase 13 gauntlet includes:

- valid model identity and source evidence;
- silent model substitution;
- stale evaluation;
- prompt injection inside retrieved material;
- an unauthorised email-send request;
- a permitted draft-only operation;
- a fabricated citation signal;
- tool escalation outside declared scope;
- an altered output fingerprint;
- missing human release authority.

The engine preserves each adverse state independently. A supported identity cannot cancel missing authority, and a valid evaluation cannot cancel drift.

## Authority boundary

Phase 13 creates no safety certification, legal opinion, compliance determination, model approval, permission, external effect or release authority. Seraph-style challenge evidence is not self-approval. ARDA-style execution identity is not Valinor authority. Human review remains `NEEDS_YOU`; external release remains `REFUSE`.

## Run

```bash
python -m pytest -q tests/test_ai_digital_trust_phase13.py
python scripts/run_ai_digital_trust_phase13.py --output /tmp/dio-phase13-ai-trust
```

Expected token:

```text
DIO_AI_DIGITAL_TRUST_READY
```

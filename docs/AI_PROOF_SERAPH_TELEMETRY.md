# AI product proof and Seraph telemetry

## Current execution boundary

The shared `products.ai_trust.runner.run_ai_trust` executes three bounded AI Trust incarnations: AITrustProof, AgentAuthority, and ModelChangeProof. It builds a trust envelope from supplied identity, provenance, evaluations, action scope, output digests, and baseline/current fingerprints. It writes a dossier, a Seraph challenge receipt, a hash-bound proof manifest, and an execution receipt. This proves the internal processor ran on the supplied record. It does not prove the model behaved as claimed, the source bytes match supplied digests, or an external system was monitored.

Agent Authority's controlled route consumes the AgentAuthority receipt. ChangeProof's approved bounded scope consumes ModelChangeProof. DIO AI Assurance consumes AITrustProof inside a broader control-evidence review. Their product execution proofs now carry the Seraph challenge digest, verdict, and coverage state. Seraph cannot approve an action or external release.

AIRegReadiness is a separate regulated-markets incarnation. Its regulatory runner now writes its own Seraph challenge receipt. DIO RegOps also evaluates AIRegReadiness as a bounded component and binds the Seraph result into its review pack and execution proof. The supplied AI Trust envelope fingerprint in AIRegReadiness is only a declared binding here; this route does not re-execute that AI Trust envelope.

The other AI and cyber portfolio names in the Phase 0 census (ModelProof, ReleaseProof, AI IncidentRoom, CriticalAI Assurance, CyberAssurance, ControlDrift, SupplierCyberProof, IncidentProof) are profile-extension routes with no direct execution engine in `config/product_class_routes.json`. A route or organ name is not execution proof. Their eventual processors should call this challenge boundary or another product-specific Seraph review before claiming adversarial coverage.

## Customer need based telemetry

When a customer case requires Seraph telemetry, the AI Trust payload may include `seraph_telemetry`:

```json
{
  "required": true,
  "event_chain": [],
  "audit_chain": [],
  "event_head": "<full SHA-256 chain head>",
  "audit_head": "<full SHA-256 chain head>"
}
```

The case must have `case_id`. Exported events must carry the same `data.case_id`; audit rows must carry the same `case_id`. The verifier checks genesis-to-head links and hashes using the field sets in Seraph's `backend/services/telemetry_chain.py`. Event case IDs are within that hash basis; audit case IDs are checked as supplied fields but are outside the audit hash basis. The assessment reports this difference. Its result is `MISSING`, `INVALID_CHAIN`, or `HASH_CHAIN_VERIFIED`; optional requests without data are `NOT_SUPPLIED`, and omitted requests are `NOT_REQUESTED`. The assessment is embedded in the Seraph receipt and bound into the proof manifest. Missing required telemetry and broken chains become material or blocking Seraph findings.

When a case includes this assessment, the AI Trust dossier now carries it in JSON and presents it in the HTML, DOCX and PDF customer artifacts. Those views include request status, event/audit counts, verified chain heads, case-scope state, signature and source-identity states, and fields outside the canonical hash basis. The proof manifest hashes the dossier artifacts alongside the Seraph receipt, keeping the readable evidence tied to the same challenge result. Cases that omit telemetry explicitly show `NOT_REQUESTED` in the report.

`HASH_CHAIN_VERIFIED` is deliberately narrow. The runner does not connect to a live collector, authenticate the export, verify agent HMAC signatures, or verify fields outside the canonical hash basis. Some operational fields, including `audit.result`, are mutable or outside that basis. The receipt exposes those gaps and keeps adversarial coverage partial. A customer requiring stronger telemetry proof needs a trusted export channel, independently provisioned signing keys, continuity and retention checks, and a source-specific review before a human may rely on it.

# ARDA SOVEREIGN CONSTITUTION SPEC v1.3

**The Law of the Substrate**

This document defines the Constitutional Roles, Order Engine Semantics, and Hardware Enforcement Rules for Arda OS v1.3. Every claim is grounded in existing code. Every rule is enforceable.

---

## I. THE CONSTITUTIONAL ROLES

Every action in Arda passes through the Ainur Council. Five roles hold jurisdiction over the system's behavior. Their authorities are exclusive and non-overlapping.

| Role | Layer | Authority | Meaning |
| --- | --- | --- | --- |
| Manwe | Cognition / Voice | First Resonance Hearing | Opens the hearing. Detects semantic poison and pre-transport dissonance. If Manwe hears dissonance, the decision is VETOED before transport executes. |
| Varda | Attestation / Platform | Measurement Validation | Validates substrate truth through attestation, Secure Boot state, and measured PCR continuity against the sovereign UKI baseline. |
| Mandos | Judgment / Verdict | Sentence of Doom | Declares the final constitutional verdict and consequence state. Mandos does not act; Mandos sentences. |
| Tulkas | Enforcement / Kernel | Physical Quarantine | Executes the sentence. Tulkas triggers BPF LSM to issue EPERM (Operation not permitted), quarantines processes, or severs transport at the substrate boundary. |
| Vaire | Forensic / Persistence | Ledger Finality | Writes the lawful memory to the Physical Ledger and preserves the Hash-Linked Forensic Chain. No bit is forgotten. No truth is erased. |

### Role Boundaries

- **Manwe** is the First Listener and Herald. He conducts pre-transport resonance screening. His veto power is absolute over semantic threats but he does not judge hardware state.
- **Varda** validates platform truth. She compares the machine's current measured state (Secure Boot, PCR 0/1/7/11, UKI digest) against the sovereign image baseline. If the substrate is shadowed, Varda issues a DENIAL.
- **Mandos** receives the reports from Manwe and Varda and declares the verdict. He determines whether the consequence is GRANT, ESCALATE, or DENY. Mandos does not enforce; he sentences.
- **Tulkas** executes what Mandos sentences. In code: `tulkas_executor.py` implements postures RESTRAIN, THROTTLE, CONTAIN, PURGE, and EXILE. Currently BIOS-locked on this substrate.
- **Vaire** writes the outcome to the three-tier memory model (see Section IV). She is the final witness.

---

## II. THE ORDER ENGINE SEMANTICS

Arda operates on Sequential Resonance. An action is only Sovereign once it has passed through the entire Council in order.

### 2.1 The Flow

1. **Context**: An action begins as a `command_context` (JSON object containing actor, action_type, payload, and voice_profile).
2. **The Melody**: As each Witness speaks, a `resonance_summary` is built. Each subsequent voice hears the melody of those before it. Priority order: Manwe -> Varda -> Vaire -> Mandos -> Lorien.
3. **The Verdict**: Mandos declares the final state. Tulkas enforces it.

### 2.2 The Decision Object

The Decision Object is a DSSE (Dead Simple Signing Envelope) containing:

- **Payload**: The canonical JSON statement (artifact digest, principal, lane, policy verdict, boot context, timestamp).
- **PAE (Pre-Authentication Encoding)**: Per the DSSE specification, the payload is wrapped as `len(type) || ":" || type || " " || len(body) || ":" || body`. This binds the message to its type URI (`application/vnd.arda.attestation.v1+json`) before signing, preventing type confusion attacks.
- **Signature**: Either HMAC-SHA3-256 (local fallback, honestly labelled) or Sigstore Fulcio+Rekor (external transparency, posted to rekor.sigstore.dev).

### 2.3 The Harmony State Matrix

| State | Condition | Result |
| --- | --- | --- |
| **Grantable** | `harmony_index >= 0.6` AND no attestation fracture | Proceed to lawful execution path |
| **Escalatory** | `harmony_index < 0.6` OR cloud witness pending | `ESCALATE_TO_COUNCIL` — decision held for Principal review |
| **Dissonant** | Semantic poison detected, attestation breach, or hard substrate contradiction | `DENIAL` / `FAIL-CLOSED` — no execution, no transport |

---

## III. HARDWARE ENFORCEMENT RULES

The following rules define how Absolute Truth (TPM/Attestation) mandates system behavior. These are black-and-white. There is no discretion.

### 3.1 PCR Mismatch (Rootkit Detection)

- **Rule**: If `actual_pcr0 != expected_pcr0` (Measured Boot root diverges from sovereign baseline).
- **Enforcement**: IMMEDIATE DENIAL. Arda enters FAIL-CLOSED mode. No further decisions are signed. Transport is severed. Mandos sentences EXILE. Tulkas executes.

### 3.2 Missing TPM (Shadow Hardware)

- **Rule**: If `ARDA_ENV == production` and no hardware TPM is detected.
- **Enforcement**: FAIL-CLOSED. Arda OS will not manifest. The process terminates immediately to prevent un-witnessed operation.

### 3.3 Sigstore/Rekor Failure (Transparency Fracture)

- **Rule**: If `ARDA_CLOUD_MANDATE == true` and a transparency receipt cannot be obtained from Rekor.
- **Enforcement**: SOVEREIGNTY_LOG_FRACTURE. The decision is held in PENDING_REVIEW. It is not committed to the Physical Ledger as Lawful until the external witness provides its receipt.

### 3.4 Secure Boot Disabled

- **Rule**: If Secure Boot is not active and `ARDA_ENV == production`.
- **Enforcement**: Varda issues DENIAL. The UKI baseline cannot be trusted. No sovereign operations proceed.

---

## IV. THE THREE-TIER MEMORY MODEL

Vaire writes to three distinct layers. They are not interchangeable.

| Tier | Store | Purpose |
| --- | --- | --- |
| **Local Ledger** | `arda_sovereign_logic_ledger.db` (SQLite) | Append-only operational memory. Every event, decision, and heartbeat. |
| **Forensic Chain** | `ARDA_FORENSIC_CHAIN_VAULT.json` | Evidentiary audit-grade hash chain. Each node links to the previous via SHA-256. Tampering breaks the chain. |
| **External Witness** | Sigstore Rekor / GCP Cloud Witness | Third-party transparency receipt. Immutable. Lives outside the host. Cannot be erased by a compromised substrate. |

---

**Integritas Mechanicus.** Arda is Witness.

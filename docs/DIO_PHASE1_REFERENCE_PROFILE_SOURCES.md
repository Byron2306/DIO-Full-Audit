# DIO Phase 1 Reference Profile Sources

Version: 1.0.0
Status: INTERNAL_REFERENCE
Purpose: Provide an explicit internal semantic source for the first six Phase 1 profiles used to prove the profile architecture. These sources are not external legal, regulatory, standards, accreditation or professional authority.

## 1. Project Delivery Domain

Canonical entities:
- agreement
- party
- obligation
- deliverable
- milestone
- dependency
- acceptance criterion
- evidence item
- exception
- change
- deadline
- responsible role

Canonical risk boundary:
DIO may normalize and track project-delivery semantics, but fulfilment, acceptance, legal effect and contractual interpretation remain with authorised humans.

## 2. Generic Contract Obligation Framework

The generic contract framework exists only to test reusable obligation semantics. It recognizes:
- deliverable obligations
- reporting obligations
- payment-related obligations
- notice obligations
- acceptance obligations
- dependency obligations
- confidentiality-related obligations
- milestone obligations

Supported deadline forms:
- absolute date/time
- recurring period
- relative to a named event
- no explicit deadline

Conservative states:
- unverified
- satisfied
- partial
- missing
- contested
- expired
- not_yet_due
- needs_review

Forbidden conclusions:
- legally_compliant
- legally_valid
- enforceable
- breached
- waived
- legally_satisfied

Those conclusions require an authorised human or qualified external authority.

## 3. Contract Owner Authority Profile

The contract owner is the human role responsible for reviewing obligation state, confirming organisational responsibility, approving evidence acceptance for the configured workflow, and deciding whether an output may proceed to release.

This profile does not create the role, identity, delegation or legal authority. Those must be supplied by the organisation and remain subject to DIO authority controls.

## 4. Files Connector Pack

The Phase 1 files connector profile is read-first. It may reference authorised files and hashes as evidence inputs.

Read capability:
- enumerate explicitly supplied files
- read authorised file content
- preserve source references
- preserve content hashes where available

Write capability:
- disabled in the reference profile

External send, publication, deletion and mutation:
- disabled

## 5. Evidence Pack Output

The reference evidence pack may contain:
- requirement or obligation ledger
- evidence map
- missing-evidence register
- contradiction or contested-state register
- deadline register
- human-review register
- provenance manifest
- release receipt when separately authorised

The pack must distinguish observed evidence, inferred mappings, human decisions and unresolved gaps.

## 6. Internal Proof Commercial Policy

The internal-proof policy is not a public offer.

It permits:
- controlled synthetic fixtures
- internal operator review
- deterministic acceptance testing
- proof-room generation for internal inspection

It prohibits:
- public marketing claims
- customer charging
- external delivery
- autonomous release
- claims of customer validation, repeatability, economic proof or scale readiness

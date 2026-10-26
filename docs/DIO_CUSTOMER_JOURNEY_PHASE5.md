# DIO Customer Journey Spine — Phase 5

## Deliverable Manifest & Release v2

**Status:** PASS / VERIFIED locally

**Acceptance token:** `DIO_CUSTOMER_JOURNEY_PHASE5_DELIVERABLE_RELEASE_V2_VERIFIED`

Phase 5 removes the legacy assumption that customer fulfilment is one PDF. It consumes the canonical Phase 4 `dio.fulfilment_result.v1` at `REVIEW_READY` and projects the held result into one format-neutral, hash-bound `dio.deliverable_manifest.v2` containing one or many customer artifacts.

## Canonical flow

```text
Phase 4 FulfilmentResult
        ↓
REVIEW_READY
        ↓
DeliverableManifest v2
        ↓
exact manifest SHA-bound human approval
        ↓
ReleaseAuthority v2
        ↓
rehash every artifact before transport
        ↓
injected delivery transport
        ↓
DeliveryReceipt v2
        ↓
DELIVERED
```

## Schemas

### `dio.deliverable_manifest.v2`

The manifest binds:

- Journey case and product identity;
- Phase 4 fulfilment request/result lineage;
- every artifact ID and kind;
- absolute artifact path used by the current controlled runtime;
- filename/logical name;
- MIME type;
- exact SHA-256 and byte length;
- purpose;
- customer visibility;
- provenance/proof binding;
- release conditions;
- source/derivation lineage;
- a canonical manifest SHA-256.

Every manifested artifact must still be `HELD`. Building a manifest creates no release, send, payment, spend, or generic authority and leaves the case at `REVIEW_READY`.

### `dio.release_authority.v2`

Release authority exists only after a resolved `fulfilment_release_review` `Needs You` item records `APPROVE` and its resolution evidence contains the exact manifest SHA-256. Authority is bound to:

- one customer case;
- one product;
- one manifest ID and SHA-256;
- one human approval record;
- an explicit set of permitted delivery channels;
- one-use consumption semantics.

Creating authority advances the strict Journey Core stage from `REVIEW_READY` to `RELEASE_APPROVAL`.

### `dio.delivery_receipt.v2`

Delivery uses an injected transport boundary. Immediately before transport, Phase 5 reopens every artifact and recomputes its SHA-256. Any post-approval byte change refuses the send before the transport is called.

A failed transport attempt:

- creates no delivery receipt;
- does not consume release authority;
- does not set `DELIVERED`;
- persists the failed attempt for operator evidence.

A successful transport must return provider receipt evidence. Phase 5 then records the exact delivered manifest SHA, channel, destination, artifact IDs, filenames, MIME types, byte counts and SHA-256 values, consumes the release authority, clears active send authority on the case, and advances `RELEASE_APPROVAL -> DELIVERED`.

Replay of consumed authority is refused.

## Format neutrality

The Phase 5 contract does not branch on PDF, ZIP, DOCX, XLSX, MP4, captions, images, or any other MIME type. A mixed pack uses the same manifest and release machinery provided every artifact has explicit custody metadata and a verified content hash.

## TDD evidence

Initial RED failed during collection with:

```text
ModuleNotFoundError: No module named 'presence_core.deliverable_release_v2'
```

After implementing the v2 contract:

```text
8 passed in 0.10s
```

Compatibility sweep across Phase 4, Phase 5, legacy single-PDF release, delivery completion and Presence bridge completion:

```text
21 passed in 0.52s
```

## Explicit non-claims

Phase 5 does not:

- wire Vesper into the Journey Core runtime;
- perform a real public Telegram/email/web send;
- replace or delete the legacy `presence_core/fulfilment_release.py` path;
- prove every one of the 68 products already emits complete Phase 5 artifact metadata;
- resolve the remaining Sophia live-Qwen representative-review gauntlet;
- close the customer case after delivery.

Those remain later programme concerns, primarily Phases 6 through 8.

## Exit gate

The contract now supports N-artifact, mixed-format deliverables under one exact manifest hash, preserves human approval as a separate authority event, refuses changed bytes after approval, constrains channels, records what actually left DIO, and prevents replay of consumed release authority.

`DIO_CUSTOMER_JOURNEY_PHASE5_DELIVERABLE_RELEASE_V2_VERIFIED`

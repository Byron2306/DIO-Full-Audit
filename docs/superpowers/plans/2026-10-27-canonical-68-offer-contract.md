# Canonical 68 Offer Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every canonical product a complete, truthful, machine-verifiable customer offer contract.

**Architecture:** Build contracts from 68 explicit product proposition overlays plus canonical intake, pricing, route-proof, and release data. Compile the contract into the existing Journey binding so downstream surfaces share one source of offer truth.

**Tech Stack:** Python 3, deterministic JSON hashing, pytest

**Spec:** `docs/superpowers/specs/2026-10-27-canonical-68-offer-contract-design.md`

## Global Constraints

- Exactly 68 unique product identities.
- Commercial validation and willingness to pay remain `UNPROVED`.
- Outcomes are bounded deliverable commitments, never guaranteed customer results.
- CTA starts governed intake and creates no quote, invoice, release, or send authority.

## Review Focus

- Blank problem, outcome, deliverable, proof, price, or CTA fields.
- Generic copy that omits the exact product and scope unit.
- Any mutation of pricing or commercial-validation truth.
- Any claim of guaranteed outcome or autonomous authority.
- Non-deterministic contract hashes.

---

### Task 1: Compile truthful offer contracts

**Files:**
- Create: `products/canonical_offer_contract.py`
- Modify: `presence_core/product_binding_registry.py`
- Test: `tests/test_customer_journey_phase8.py`

**Interfaces:**
- Produces: `build_canonical_offer_contract(product, intake, archetype, route) -> dict[str, Any]`.
- Produces: `binding["offer_contract"]` for all 68 products.

- [ ] Write failing tests for completeness, identity uniqueness, bounded outcome language, proof/pricing truth, CTA authority, and deterministic hashes.
- [ ] Implement 68 product proposition overlays and the deterministic contract builder.
- [ ] Compile contracts into all bindings without changing existing pricing or release authority.
- [ ] Run the full customer-journey suite and census checks.


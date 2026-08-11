# DIO Product Manifests

This directory is the canonical composition authority for DIO products/incarnations.

A manifest states **what** a product requires: work patterns, META primitives, profile references and capability requirements. It does not hard-code organs or create executors. Compiler-generated runtime plans belong to Phase 2 outputs, not source manifests.

During Phase 0, the existing `config/dio_meta_products.json#vertical_compositions` remains a compatibility input only. New product composition truth belongs here.

If a required execution capability has no valid executor, the governed state is `REFUSE`, not an unhandled error.

# HOMS Knowledge Bank Registry

Created: 2026-08-08T08:03:41+00:00
Root: `/home/byron/Downloads/KnowEdge_AutoRelease_Suite`

## Verdict

The knowledge bank exists, but it was fragmented. This registry makes the usable layers explicit before provider-backed generation.

## Core Stores

- CAPS authority: 282 documents.
- CAPS matrix evidence: 282 documents; failures 0.
- CAPS ontology profiles: 104.
- Assessment design profiles: 104.
- Official-paper source catalogue: 9 papers.
- Curated source assets: 82 assets.
- Subject profiles: 12.

## Sophia / Mandos

- Sophia service modules present: True.
- Sophia project store events: 2075.
- Sophia project records: 123.
- Mandos relational memory wrapped/encrypted: True.

## Provider Support

- Gemini key present: True.
- Gemini default model hint: `gemini-3.5-flash`.
- NVIDIA NIM key present: True.
- Secret values redacted: True.
- NVIDIA default base URL: `https://integrate.api.nvidia.com/v1`.

## Runtime Order

1. resolve subject + grade + term
2. retrieve CAPS excerpts and canonical assessment profile
3. retrieve official-paper source/object patterns for that subject
4. retrieve HOMS correction memory and hard bans
5. construct subject knowledge packet
6. provider draft generation as JSON only
7. provider critic pass against CAPS/profile/source/format constraints
8. render only if validation passes
9. educator approval before classroom use

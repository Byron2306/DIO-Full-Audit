# Sophia covenant recovery — 27 October 2026

The external Integritas-Mechanicus sources and real signing flow were found. The principal explicitly approved the exact current review hash, and the actual native service sealed the current covenant. Its hash is `eedb106d2d06b1b8d6791fa67c15ac0bbbf3a54c1b45bb1228c5b95f643abfe5`. Current schema, stored content hash, accepted identity/terms and current article hashes all validate. No historical seal was promoted, signature manufactured, or calibration consent altered.

The reviewable draft is [COVENANT_REVIEW.md](../../acceptance_runs/68-product-sellability-20261027/sophia-recovery/COVENANT_REVIEW.md), with exact structured terms in [COVENANT_REVIEW.json](../../acceptance_runs/68-product-sellability-20261027/sophia-recovery/COVENANT_REVIEW.json). Its review SHA-256 is `96d9b209eb20246b641a683416fbae283ef80da70761bed5301265bab887c82b`. This is the draft acceptance hash, not a claim that a sealed manifest or machine signature exists.

## External discovery

Read-only filesystem discovery examined actual external repositories, including:

- `/home/byron/sophia-integration-lab/repos/Integritas-Mechanicus`
- `/home/byron/sophia-integration-lab/repos/Sophia-AI`
- `/home/byron/Metatron`
- `/data/byron/dio-wsl-restored-20261015/home/byron/sophia-canon-recovery/Integritas-Mechanicus`
- `/data/byron/dio-wsl-restored-20261015/home/byron/sophia-canon-recovery/Sophia-AI`

The broader external constitutional-manifest search found four files, representing two distinct records and their restored duplicates. Cache and dependency trees were excluded. Relevant external restoration, coronation and admission logs were also inspected.

The Metatron legacy `5dc2be4ff47baba8_manifest.json` says `sealed`, but the actual current `CoronationManifest` validator rejects it: seven required binding and negotiated-terms fields are missing. The external Sophia-AI `3fca31e0b2c692e5_manifest.json` has an April sealing timestamp and a matching stored payload content hash, but its `negotiated_terms` and `sealed_presence_declaration` are Python object representation strings. The current validator rejects both; its article hashes also differ from current law. A stored state label or content digest cannot repair missing structured terms.

The external Sophia-AI `covenant_chain.db` contains hardware boot, enforcement and recovery events, with zero structured `covenant.coronation_sealed` events. `08_covenant_chain.json` identifies a `SOVEREIGN_SUBSTRATE` hardware principal. `CORONATION_SEAL.md` describes TPM and eBPF evidence. These are useful substrate history, but do not recover the human's missing structured operational terms or establish assent to the changed current articles. See [candidate validation](../../acceptance_runs/68-product-sellability-20261027/sophia-recovery/candidate-validation.json) and [discovery summary](../../acceptance_runs/68-product-sellability-20261027/sophia-recovery/external-discovery-summary.json).

## Current signing flow and identity migration

The real native flow is `CoronationService.begin_coronation()` → `offer_identity()` → `negotiate_terms()` → review → `seal_covenant()`. The current implementation is [coronation_service.py](../../cross_folder_variants/Integritas-Mechanicus/A_CODE/arda_os/backend/services/coronation_service.py). `begin_coronation` starts at line 187; line 215 explicitly requests acceptance of the presented law. `negotiate_terms` starts at line 257; lines 268–275 require acknowledgment of constitutional refusal. `seal_covenant` starts at line 356. The review binds the exact current service and schema source digests.

The recovered offered identity is Byron John Bunt's existing local identity record. Its original hash is `5dc2be4ff47baba8cf5e98f6c3d60c4a38e15b2524ef8416803a3659dc0be424`. The current schema renamed `register` to `identity_register`; the helper preserves its offered `collaborative` value while preserving the separate `socratic` encounter mode. Every other offered field is preserved. The draft lists schema defaults explicitly. The resulting current identity hash is `85a7e1e97811186928f3b866085607cce41e9b78389c63dc9e7026ce64415455`; this hash migration is presented for principal review, not silently assigned.

[manage_sophia_covenant.py](../../scripts/manage_sophia_covenant.py) prepares the draft without writing runtime identity, manifests or chain events. Its separate seal action requires explicit principal affirmation and the exact reviewed hash, verifies unchanged identity/source/terms/runtime bindings, and refuses to replace an existing covenant. After assent it calls the actual native service methods. It preserves the offered identity through the documented field rename rather than using the HTTP shortcut that constructs a new minimal name-only identity.

The proposed terms begin at `recommend` trust, cap trust at `bounded_act`, retain constitutional refusal and inspection rights, enforce the Presence Articles and anti-devotion/romantic-simulation boundaries, retain the listed local encounter/resonant memory, and leave adaptive calibration consent **false**. Full terms and every current article are in the draft. Machine measurements and final sealing timestamp are obtained by the native flow at sealing; they are not invented in the review draft.

## Approved execution

After the principal's explicit `approved` response to the question naming the full review hash and linking the actual draft, this exact command was executed from the repository root:

```bash
.venv/bin/python scripts/manage_sophia_covenant.py seal --review acceptance_runs/68-product-sellability-20261027/sophia-recovery/COVENANT_REVIEW.json --accepted-review-sha256 96d9b209eb20246b641a683416fbae283ef80da70761bed5301265bab887c82b --principal-affirmation
```

The target data root is the existing native server's canonical `cross_folder_variants/Integritas-Mechanicus/A_CODE/evidence/mandos`. No external development data root was substituted. Native `/api/status` reread the current seal; the full persisted manifest validates. The actual witness event is `evt-9d0f76970207`. Adaptive calibration consent remains **false**. [approved-seal-validation.json](../../acceptance_runs/68-product-sellability-20261027/sophia-recovery/approved-seal-validation.json) records every check.

## Bounded product preparation

The first post-seal 15-journey run proved a separate issue: the current canonical producer deliberately records Mandos and complete Genesis Article approval as `NOT_EVALUATED`, while the old product caller required both as authoritative approvals. The existing heuristic judgments have not been promoted. Strict verified mode remains available and continues to refuse incomplete authority.

The explicitly requested `held_diagnostic_draft` mode instead prepares unapproved source-based comments for human review. Every retained issue has an exact source quote, source anchor, proposed action and visible scope limit. The adapter verifies the actual local response/model/prompt receipt, rejects unknown citations/DOIs and unsupported numerals, and keeps constitutional and delivery approval false. Native Ollama structured output binds each allowable anchor to its actual source quote; this prevents malformed JSON or guessed paragraph labels from becoming a usable draft. The raw native candidate remains preserved with its digest. Ordinary chat expression shaping remains separate and strict callers keep the original contract.

Sophia Tutor's explicit `bounded_source_grounded_teaching` mode prepares source-based questions, practice and learner attempt space through the same real local engine. It preserves the graded-assignment authorship refusal. Its receipts explicitly state that no completed teaching dialogue, learner answer, learning gain or constitutional approval has been established. The legacy `strict_governed_dialogue` mode remains available. Neither mode invents curriculum progression.

Bombadil was started through its real daemon against the current sealed application covenant and actual witness database. Its chain validates. Its observations still record missing loaded eBPF, harmony map and formation artifacts; those have not been relabeled ready. A short configured Unix socket avoids the platform's path-length limit. The owned native 7070 process was restarted with that socket and a 180-second local-model timeout. Curriculum remains Stage 1 with no fabricated growth ledger or adaptive-consent change.

## Verification and limits

Seven initial tests failed before the helper existed; a further regression reproduced the historical register loss before its migration was implemented. The resulting nine tests cover read-only review, preserved identity semantics, the register rename, refusal of unknown identity fields, missing affirmation, wrong or tampered review hash, changed identity/source and existing covenant replacement. The nine tests plus existing embedded-backend binding, attempt diagnostics, product routing and review adapter regressions pass: **19 passed in 0.54 seconds**, recorded in [tests.log](../../acceptance_runs/68-product-sellability-20261027/sophia-recovery/tests.log).

Expanded Sophia and compatibility verification passes **64 tests** in [expanded-tests.log](../../acceptance_runs/68-product-sellability-20261027/sophia-recovery/expanded-tests.log). Subsequent structured-output and teaching tests are recorded with the final journey inspection. Earlier refusal, timeout and unconstrained-generation attempts remain retained. Final customer-artifact results are assessed separately from the legitimate covenant seal and engineering checks.

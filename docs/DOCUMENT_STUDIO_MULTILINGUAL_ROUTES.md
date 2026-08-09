# DIO Document Studio Multilingual Routes

## Configured Languages

| Language | Locale | Current evidence | Commercial status |
|---|---|---|---|
| Afrikaans | `af-ZA` | Controlled pack with recorded language-practitioner approval | Independent validation and remaining product gates still required |
| isiZulu | `zu-ZA` | Dual-pass NVIDIA NIM pack with recorded language-practitioner approval | Independent validation and remaining product gates still required |
| Sesotho | `st-ZA` | Dual-pass NVIDIA NIM pack with recorded language-practitioner approval | Independent validation and remaining product gates still required |
| Setswana | `tn-ZA` | Dual-pass NVIDIA NIM pack with recorded language-practitioner approval | Independent validation and remaining product gates still required |

The canonical registry is `config/document_studio_languages.json`. It also normalises common labels such as `Zulu`, `Sotho`, `Tswana`, and the misspelling `setstwana`.

All four lanes now belong to one semantic object: `state/lingua/objects/DIO-LINGUA-WATER-001.json`. The object stores seven typed source units, source hashes and versions, per-language status, provider provenance, reviewer authority and unit-level staleness.

## Production Route

```text
authorised controlled source
  -> canonical language profile
  -> NVIDIA NIM DeepSeek V4 first draft
  -> independent DeepSeek semantic critic
  -> number and protected-token validation
  -> bilingual review pack and terminology ledger
  -> proficient target-language reviewer
  -> subject owner
  -> client approval
  -> release
```

The active NIM model is `deepseek-ai/deepseek-v4-flash-0731`. The unversioned `deepseek-ai/deepseek-v4-flash` endpoint reached end-of-life on 7 August 2026 and must not be restored as the default.

## BEAST Authority Split

BEAST is the crystallisation authority, but not every crystal requires a human.

BEAST learns automatically from:

- anchor-completeness checks;
- numeral and protected-token enforcement;
- source-hash staleness;
- hard deterministic validation failures;
- recurring medium/high language-risk flags that should force review.

Those crystals encode constraints and conservative routing. They do not claim that any translation is correct. The current proof generated 16 language-specific deterministic guards and 13 conservative risk patterns without operator intervention.

Human approval is required only before BEAST crystallises semantic truth:

- an approved target-language term;
- an approved complete translation unit;
- an institution-specific terminology choice.

The bridge is `scripts/lingua_beast_bridge.py`. It uses BEAST's durable semantic credits, crystal chain, evidence scorer, Chronicle, negative-capability store, capability-learning ledger, Memory Hull and PREC lifecycle store. `scripts/approve_lingua_crystals.py` rejects incomplete approvals, verifies source hashes, crystallises approved units, reconciles pack-level QA, and writes the BEAST receipt. Machine drafts cannot enter active semantic reuse.

The Control Deck exposes this split in its **Lingua QA** tab. Deterministic guards and medium/high uncertainty patterns are ingested without human intervention and shown as BEAST credit counts. Language-review work is grouped by semantic object; the operator is not asked to approve every flag. Only the final decision that wording or terminology is semantically authoritative creates reusable translation-unit or terminology credits.

When a source unit changes, only translations aligned to that source hash are marked `stale_source_changed`. Unchanged units remain available for review or verified reuse.

## Proof Candidates

- `deliverables/document_studio/DIO-DOC-ISIZULU-001`
- `deliverables/document_studio/DIO-DOC-SESOTHO-001`
- `deliverables/document_studio/DIO-DOC-SETSWANA-001`

Each pack contains aligned DOCX and PDF copies, visible redline, bilingual review, glossary, QA, provider output, receipt, proof image, and release ZIP. All three preserve all seven paragraph anchors, operational numbers, `pH`, `NTU`, `QMS-07`, and `PBT`.

## Honest Quality Finding

Automated integrity passed for all three routes. A language-practitioner approval was recorded through the Control Deck for all four controlled lanes on 9 August 2026. That advances semantic authority but does not certify the translations or satisfy separate technical-editor, client, educator, or delivery approvals.

The provider still produced uncertain or incorrect specialised wording. In particular, the Setswana candidate's rendering of `authorised official` is flagged as unsuitable and the pack remains blocked. The critic exposes review points but cannot serve as native-speaker approval.

No public claim should say these languages are automatically translated, certified, or ready for unsupervised release. The commercial offer is BEAST-governed multilingual production plus qualified review, with approved knowledge reused rather than repeatedly reinvented.

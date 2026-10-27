# Lingua → Document Studio Afrikaans integration, 27 October 2026

Lingua now provides an actual reusable translation path, including a dedicated local English-to-Afrikaans machine translation engine. It improves several previously garbled outputs, but neither a successful render nor a clean integrity check establishes professional Afrikaans quality. No generated translation was promoted to human approval.

## What was wrong

The prior Document Studio path called a document-level small general-purpose language model before applying existing approved Lingua memory. Its second pass blindly replaced drafts, even when that pass was less faithful or returned English. Number/name checks passed while invented Afrikaans remained in customer-facing DOCX files. The previous canonical audit records examples such as `apointmentsprosesie` and `kwartaal beoordela`.

Actual investigation also exposed two distinct problems in the dedicated MT experiment. OPUS Marian is trained for sentence translation; giving it several sentences together could omit later instructions. Forcing long exact phrases through constrained beam search sometimes caused invented suffix text. These failed experimental runs are retained under `acceptance_runs/68-product-sellability-20261027/lingua-afrikaans/`, including `marian-local`, `marian-final`, and `marian-corrected`. They are not passing evidence.

## Implemented behavior

- `adapters/lingua/document_translation.py` resolves exact current-source, human-approved BEAST units before generation. Partial memory generates only missing paragraphs. Stale source hashes, other target languages, and machine states do not create reuse authority.
- A reusable explicit `lingua_translation_backend=marian_local` option runs the pinned Helsinki-NLP English-to-Afrikaans model locally. The request's Ollama model remains unchanged for technical editing and optional criticism. Existing requests can retain the declared Ollama translation backend.
- The MT subprocess translates each sentence inside its governed paragraph separately, preserving paragraph identity. Protected names, quoted terms and applicable target terminology use reversible placeholders. Placeholder loss/duplication fails that candidate. Original numeric identifiers stay in the sentence; whitespace-only changes can be restored to the exact protected token.
- Generation has at most two attempts, bounded token budgets and 90-second local subprocess/network limits. Paragraph length beyond the MT context fails explicitly.
- Diagnostics check missing/added numbers, protected tokens, relevant terminology, visible negation, unexpected scripts, English residue and model commentary. These are rejection signals, not a language-quality score. Real freezer-source testing demonstrated that grammatical and semantic defects can remain despite clean deterministic diagnostics.
- The optional independent language critic retains provenance and cannot replace a fact-preserving candidate with a revision that fails deterministic checks. Dedicated MT text is diagnostic-only by default for the weak Ollama reviewer; enabling replacement requires an explicit request setting.
- Technical editing now protects both sides of a supplied bilingual glossary. Approved original-source memory cannot overwrite a translation after the source paragraph has been edited. Lingua source hashes now identify the controlled source actually translated.
- Translated title/subtitle handling is localized, and the pack contains `LINGUA_HUMAN_REVIEW_TEMPLATE.json`. The template records actual paragraph source hashes, candidate text and unresolved flags; reviewer identity is blank and approval remains pending. It fits the existing explicit human crystallization workflow.

## Local engine and reproducibility

Model: [Helsinki-NLP/opus-mt-en-af](https://huggingface.co/Helsinki-NLP/opus-mt-en-af), Apache 2.0, pinned revision `6bb29b2752ad425fae1ecdaba201e2de636ecc24`. Public setup downloads approximately 297 MB of weights. The versioned `adapters/lingua/LOCAL_MT_MODEL_LOCK.json` pins all downloaded file SHA256s. Runtime checks the installation manifest against the repository lock and the actual files.

The isolated environment is `~/.cache/dio/lingua-mt/venv`; runtime dependencies include CPU PyTorch 2.14.1, Transformers 4.48.3, SentencePiece 0.2.2 and sacremoses 0.2.0. Transformers 4.57 was deliberately replaced because its constrained-search path required separately downloaded remote code. No remote model code is enabled here. `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and `local_files_only=True` apply during customer inference. Public model setup is a separate operation and does not accept customer text.

Reproduction instructions are in `adapters/lingua/LOCAL_MT_SETUP.md`. `MODEL_MANIFEST.json` and `MT_RUNTIME_REQUIREMENTS.txt` under the acceptance folder retain the installed model and environment evidence.

## Actual unseen comparison

`UNSEEN_ENGINE_COMPARISON.json` records a previously unseen freezer procedure with time `07:15`, threshold `-18`, batch `LC-204`, negation and a supervisor instruction. The real Granite 3.2 response included `vrieskryo-temperatuur`, `Wy die leesing` and `leidingenaar`. Sentence-level Marian produced:

> Die tegnikus moet die vrieskastemperatuur teen 07:15 opneem. As die lesing bo -18 grade Celsius is, moet jy nie vrag LC-204 vrylaat nie. Bel die opsiener voordat hy enige voorraad verskuif.

This is a material improvement in comprehensibility and preserves the visible time, threshold, identifier and prohibition. It still needs review: `vrag` is questionable for a production batch, and `hy` introduces an actor interpretation in the final sentence. The actual Ollama critic attempted a revision that changed the time formatting, retained English and lost visible negation; the path rejected that revision. Its self-reported `acceptable` assessment was not treated as approval.

## Verification

Focused translation/lifecycle/Document Studio suite: **33 passed and 7 subtests passed**. Tests cover unseen input, partial exact memory, stale source, other-language memory, no machine-to-human promotion, bilingual glossary protection, edited-source memory mismatch, protected placeholders, sentence segmentation, bounded resampling, explicit backend selection, model-file tampering, bad critic revisions, and accurate critic provenance. Red runs were observed before the principal new behaviors were implemented.

The broader Lingua + Document Studio suite completed with **95 passed, 7 subtests passed, 1 failed**. The failure was outside these changes: `tests/test_lingua_storyline_semantic_diversity.py::test_vertical_story_remains_semantically_distinct_and_governed`, expecting scene focus `promise` where the current storyline returned `outcome`. The full log is `REGRESSION_TESTS.log`. This is not represented as a green suite.

## Customer artifact runs and quality judgment

Final artifact inspection and case outcomes are recorded in the acceptance run summary and inspection report alongside this audit. Translation-only runs explicitly select `service=translation` to exercise localization independently from the slower original Ollama English-editing phase; full `edit_and_translate` runs are separately labeled. No acceptance input or output was represented as human reviewed.

The correct commercial claim is a governed localization drafting and review workflow, with reusable already approved memory and an improved dedicated local MT candidate. An unattended professional translation claim is not supported. A proficient Afrikaans reviewer must correct terminology, grammar, actor/negation details and every final paragraph before release. Existing genuine human-approved units can be reused for exact unchanged source text; AI candidates cannot.

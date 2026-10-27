# Independent review of the 68-product execution integration

Reviewed the uncommitted production changes against `2ece3d4b`, including the new native-content extractor, the execution design and plan, and the added source-binding regressions. This review excludes pre-existing telemetry symlink effects and backup files. It is a code/integration review, not professional acceptance of the 68 deliverables.

**Disposition at initial review: changes required.** Four important findings are reproduced below. No critical external-authority bypass was identified in the reviewed changes. The explicit held/review boundaries, separate accreditation criteria, and distinction between controlled formatting and historical canon proof are improvements.

## Important findings

### R1 — Prepared execution recomputes hashes instead of verifying the native receipt (P1)

**Location:** `products/professional_evidence_prepared_executor.py:78-88`, invoked at line 156 in the reviewed version.

`_finish_native_artifacts` scans the files that happen to remain under `EXECUTION`, creates new hashes for them, and never receives the native route result/receipt. Therefore a missing declared native artifact is silently omitted, and changed native bytes receive a new valid hash. The low-level finisher's correct hash check cannot detect either condition through this integration.

**Reproduced with the actual Offer Lab route:** wrap `_route_execute`, call its original implementation, then either (a) delete `BOUNDED_OFFER.json` or (b) replace `BOUNDED_OFFER.md` with `Corrupted customer offer. Price is R999999.` before returning its unchanged result. Calling `execute_prepared_customer_case` on a freshly materialized Offer Lab packet returned `PASS_FULL_PIPELINE`, with a successful shared finish, in both cases. The native receipt still records the original paths/hashes. The blind review does not check those bytes.

**Minimal fix:** pass the native result to the finishing adapter and verify its declared artifact inventory against retained bytes before selecting renderable renditions. Fail on missing or changed declared artifacts, including non-prose deliverables. Explicitly distinguish any additional derived/discovered files from receipt-verified outputs. Add integrated regressions for the two mutations above; the existing direct-finisher stale-hash test does not cover this seam.

### R2 — HTML extraction silently deletes table qualifications and citation destinations (P1)

**Location:** `presence_core/artifact_content.py:31-45,74-80`.

Once inside a table, text outside `td`/`th` is discarded. This includes `<caption>`, which can contain the qualification that determines how the numeric results should be interpreted. Anchor attributes are also ignored, so a source link whose visible label is `source document` loses its destination.

**Reproduction input:**

```html
<h1>Finance</h1>
<table><caption>Unaudited estimates, not approved lending values.</caption>
<tr><th>Amount</th></tr><tr><td>R100000</td></tr></table>
<p>Evidence: <a href="https://example.org/original-evidence">source document</a></p>
```

Passed this hash-bound file to the real `render_held_artifacts_for_review`. The resulting HTML retained `R100000`, omitted both the qualification and URL, and returned Format Core / Production Studio `PASS`. This violates the stated review focus that source qualifications survive rendering. Renderer QA cannot detect text removed before it receives semantic content.

**Minimal fix:** retain table captions as table titles or adjacent semantic text; preserve citation destinations as safe rendered references or visible URLs. Add a real-render regression checking these exact strings, not just numeric table cells.

### R3 — DOCX extraction detaches tables from their explanatory paragraphs (P2)

**Location:** `presence_core/artifact_content.py:124-134`.

The extractor emits every document paragraph first, then appends every table. A paragraph describing the following table can consequently qualify a different table after finishing.

**Reproduced source order:** `Approved actual figures`, table containing `R100`, `The following are unverified estimates only`, table containing `R999999`. The extracted blocks are the two paragraphs followed by the two tables. The first table now follows the unverified-estimates qualification; no paragraph separates the second table. This is substantive association loss in financial/evidence documents, even though every individual string survives.

**Minimal fix:** iterate DOCX body children in document order, emitting paragraph/table blocks as encountered. Add a regression asserting interleaved block order and the same order in the finished HTML.

### R4 — Offer Lab splits thousands-separated approved prices into different prices (P2)

**Location:** `products/professional_evidence_native.py:596-597`.

The new numeric `findall` treats every digit sequence as a separate approved option. A customer row `Approved price test options ZAR: R1,500; R2,500.` produces `[1.0, 500.0, 2.0, 500.0]` in `BOUNDED_OFFER.json` and the customer Markdown. This invents four price options rather than preserving the supplied two. A negative amount would also lose its sign.

**Minimal fix:** define and validate the supported list/currency grammar, preserve grouping separators when parsing each amount, and refuse ambiguous or invalid values rather than extracting arbitrary numbers. Add grouped-currency and invalid-value regressions alongside the existing `700, 1100` example.

## Verification performed

```text
.venv/bin/python -m pytest -q \
  tests/test_shared_production_finish.py \
  tests/test_professional_commercial_dataflow.py \
  tests/test_professional_accreditation_source_projection.py
14 passed in 3.00s
```

Additional isolated temporary-directory probes exercised the real HTML finisher, DOCX extractor, actual Offer Lab output generation, and prepared execution after native artifact deletion/mutation. No production code was edited by this reviewer; probes did not publish, send, spend, or change release authority.

## Deferred limitations

- The extractor deliberately omits figures/diagrams from semantic JSON and does not reproduce embedded document graphics. A successfully finished text review is therefore not evidence of complete visual/domain preservation. Retain that limitation in the final audit and inspect the originals for visual products.
- Markdown is currently rendered as literal line-oriented paragraphs rather than parsed Markdown. This is a presentation limitation; the reviewed line text is retained.
- This review did not rerun the complete 53-case or 68-product portfolio or repository suite. The coordinator owns those execution records and the final acceptance ledger.

The finding statuses above describe the initial reviewed snapshot. Any subsequent fixes need focused regressions and an explicit follow-up disposition before treating these findings as closed.
# Implementer resolution

The four findings were addressed after the independent review with observed failing regressions, then verified together:

- R1: prepared execution now verifies declared provider receipt/proof inventories before rendering. Deleted machine-readable output and altered native prose both refuse. Discovered derivatives are labelled separately from provider-declared artifacts.
- R2: HTML table captions and anchor destinations survive semantic extraction and rendering.
- R3: DOCX body paragraphs and tables retain source order and qualification associations.
- R4: grouped currency amounts and decimals remain complete price values.

Evidence: `acceptance_runs/68-product-integration-20261027/review-fixes-red.log`, `review-fixes-green.log`, and final `final-focused-tests.log` (135 passed). A fresh post-review 41-product/123-journey batch passed. No second reviewer pass was substituted for these regressions. The original independent findings remain below as the record of what was reproduced.

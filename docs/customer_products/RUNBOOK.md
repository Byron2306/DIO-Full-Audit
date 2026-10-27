# Source-driven DIO customer products

The local customer runner connects actual supplied sources to specialist engines and editable delivery formats. It lists all 68 offers and currently exposes explicit customer-packet contracts for 38. The other 30 retain their existing native protocols; the runner refuses them instead of substituting demonstration inputs.

From the repository root:

```bash
.venv/bin/python scripts/run_customer_product.py --catalog
.venv/bin/python scripts/run_customer_product.py \
  --product 'Contract Desk' \
  --packet config/customer_products/examples/contract.json \
  --out /tmp/dio-contract-customer-001
```

Choose a new, empty output directory for every job. The example files are synthetic acceptance material. Replace their contents with the customer's actual records and set `owner_authorized: true` only when the source owner has authorized local processing. Relative document and brand-asset paths in CLI packets resolve against the packet file's directory.

`CUSTOMER_EXECUTION_RECEIPT.json` identifies the requested product, normalized execution packet hash, actual provider receipt and file hashes. It records human review required, release not authorized and commercial validation unproved. It does not create an order, invoice approval, professional opinion, send or publication authority.

## Input and output contracts

| Contract | Runnable example | Actual output |
|---|---|---|
| Contract Desk | `config/customer_products/examples/contract.json` | Clause register, obligation candidates, bounded calendar, commercial terms and reviewer questions; DOCX/HTML/PDF and native obligation bundle. |
| Finance Readiness and its Studio | `config/customer_products/examples/readiness.json` | Separate requirement/evidence matrix, missing-document requests, source-supported calculations, XLSX and DOCX/HTML/PDF. |
| Corporate/POPIA Readiness, InvestorProof, EntrepreneurProof | Readiness contract with actual applicable requirements | Documentary presence and gaps; domain applicability and validity require the responsible reviewer. Financial calculations apply only to the declared financial services. |
| Evidex EvidenceOps | `config/customer_products/examples/evidex.json` | Full native Evidex pack plus source-record review, reported quantity comparisons, record-specific questions and customer DOCX/HTML/PDF. |
| VAMP Performance | `config/customer_products/examples/vamp.json` | Full native VAMP snapshot/Evidex handoff, source-declared review period, objective coverage and editable review document. Three native processing consents must be explicit. No rating. |
| Report & Pitch Studio / Article Publication / Article Publication Studio | `config/customer_products/examples/report_pitch.json` | Source-linked report, article draft, chart and PPTX; HTML/DOCX/PDF, claim map, reviewer checklist and ZIP. These offers share a production capability. |
| Professional Correspondence and its Studio | `config/customer_products/examples/correspondence.json` | Specific factual letter draft, source map, TXT/DOCX/HTML/PDF. Sending and concessions remain the sender's decisions. |
| FundingFinder | `config/customer_products/examples/funding_finder.json` | Applicant-specific shortlist, criterion/timing states, document requests, source snapshots, CSV/DOCX/HTML/PDF and ZIP. No application or eligibility certification. |
| Launch Studio | `config/customer_products/examples/launch.json` | Customer-brand channel creatives, copy, landing HTML, source/semantic manifest, owner schedule and ZIP. No posting, advertising spend or automatic scheduling. |
| Document Studio Edit / Localize | Native Document Studio request, including `document_path`, job ID, title and processing authority | Existing native edit/localization outputs and Lingua receipts. Localize selects the dedicated local Afrikaans translator on new requests; proficient language review remains required. |
| Existing evidence-review profiles | Separate quoted `requirements` and `evidence` using the readiness source format | Full existing governed evidence-review profile and editable matrix. A CyberAssurance profile is evidence preparation, not execution of a security scan; an AuditProof matrix is not an audit opinion. |

Quotes must match supplied source text. Requirement/evidence links name explicit IDs. Source hash mismatches are refused. Customer statements remain untrusted with unknown freshness until reviewed.

Contract dates bind only within an explicit obligation sentence. Multiple dates, relative acceptance/notice triggers and unrelated commencement dates remain questions. The native calendar is review support, not a legal deadline determination.

Report metrics require their label, value, unit and period in the same local measurement clause. Compound or negated measurements require narrower source quotations or human review. Explicit arithmetic checks periods and denominators; it does not establish causality, affordability or forecast reliability.

FundingFinder uses supplied official-page snapshots by default. The common runner never fetches public sources automatically. Its lower-level API offers explicit URL-allowlisted fetching; see the funding audit for limits. A missing or negated application window remains unknown.

VAMP accepts a source statement such as `Review period: January-June 2026.` or an ISO date range within one year. It preserves explicit objective quantities and requires a real objective. Text saying that an article or certificate exists is a documentary candidate; it is not independent inspection of that artifact. Missing scope is refused. CPD and Promotion fixture journeys without actual dates therefore remain blocked instead of receiving an invented August scope.

## Local translation and Sophia

Localize supports Lingua's exact approved-memory reuse and explicit `marian_local` translation. See [local MT setup](../../adapters/lingua/LOCAL_MT_SETUP.md). `professional_af_v1` is machine-proposed terminology, not human-approved memory. `LINGUA_HUMAN_REVIEW_TEMPLATE.json` records paragraph candidates for actual correction/approval. An unseen battery instruction exposed a remaining semantic error; an automatic integrity pass is insufficient for unattended professional translation.

Sophia's genuinely approved covenant is now sealed and recognized by the native service. Product preparation uses explicit held diagnostic mode: exact source quotes/anchors and response receipts are checked, while Mandos/complete Genesis Article approval remains `NOT_EVALUATED`. Strict approval mode retains its refusal. Tutor creates source-based practice and learner attempt space, without claiming completed dialogue or learning gain. These five products continue through their existing native protocols rather than the new generic runner.

## Reproduce acceptance

```bash
.venv/bin/python scripts/run_customer_pathway_acceptance.py --out /tmp/dio-specialist-acceptance-001
.venv/bin/python scripts/run_report_pitch_acceptance.py --out /tmp/dio-report-acceptance-001
.venv/bin/python scripts/run_customer_launch_acceptance.py --out /tmp/dio-launch-acceptance-001
.venv/bin/python scripts/run_funding_finder_acceptance.py --out /tmp/dio-funding-acceptance-001
```

LibreOffice and `pdftotext` are needed for PDF acceptance. Native Evidex uses its configured Python environment and dependencies in `cross_folder_variants/Evidex/A_CODE/requirements.txt`; the root rendering environment uses `requirements-format-core.txt` plus openpyxl/jsonschema. Lingua MT has a separately pinned offline environment. Sophia's native local service and Ollama are required for its existing review protocols.

For specialist services, `--no-pdf` skips the customer PDF renderer. Native Document Studio retains its own export contract. The output receipts and source artifacts remain held until actual professional/customer review and the existing separate release process.

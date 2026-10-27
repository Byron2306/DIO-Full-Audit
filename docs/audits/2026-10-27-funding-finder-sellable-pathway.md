# FundingFinder: source-dated customer shortlist pathway

The local `products/funding_finder_pipeline.py` service produces an applicant-specific funding research pack from actual source records. It renders an editable DOCX shortlist, HTML, PDF when LibreOffice is available, CSV, an eligibility matrix, source-byte snapshots with hashes, next-document/request actions and a controlled ZIP. It reuses existing DIO Format Core. It does not apply for funding, certify eligibility or promise an award.

## API and router contract

```python
from products.funding_finder_pipeline import build_funding_shortlist

receipt = build_funding_shortlist(
    packet, "/new/empty/output/directory",
    as_of="2026-10-27", fetch_public=False,
)
```

`packet.applicant` contains a name, sources (`source_id`, `text`) and facts (`field`, typed `value`, `source_id`, exact `quote`). `packet.opportunities` contains 1–25 records with an ID, title, funder, official URL, source content or base64 bytes and retrieval date, and source-quoted criteria. Optional records cover deadline, opening date, explicitly stated rolling timing, funding bounds, purpose, stage and required documents. Unknown or unsupported interpretations stay unresolved.

An offline router example is:

`acceptance_runs/68-product-sellability-20261027/funding-finder/reviewed/packets/south-africa-agri-live-snapshot.json`

The corresponding Moya SkillLab example is `south-africa-moya-live-snapshot.json` in the same directory. Both use explicitly synthetic applicant declarations and genuine, dated official source-byte snapshots. Neither represents actual applicant evidence or funder approval. For a small entirely synthetic packet, use `controlled-baseline.json` in the same directory.

Receipt keys are `status`, `output_dir`, `as_of`, `applicant`, `shortlist`, `deliverables`, `review_flags`, `processing`, `release`, `qa` and `artifacts`. Each shortlist row carries rank, opportunity ID, source URL/retrieval date/hash, source-quoted criterion states, funding evidence, timing, next actions and score. `deliverables` maps `shortlist_docx`, `shortlist_html`, optional `shortlist_pdf` and `shortlist_csv` to relative paths.

## What the ranking establishes

Every criterion is independently recorded as `met`, `mismatch` or `unknown` on the supplied record. A match requires both captured funder evidence and supported applicant evidence. Supported operators are equality, inequality/exclusion, membership, minimum and maximum. Missing evidence, unsupported values, ambiguous boolean interpretations and instruction-bearing source quotations cannot become matches. The parser checks explicit quoted values; a reviewer must still confirm semantic interpretation, exceptions and completeness against the full rules.

Overall classes are `appears_aligned_on_supplied_record`, `unknown_review_required`, `mismatch_on_supplied_record` and `closed_on_as_of_date`. No class is named “eligible” or “approved.” Expired and future-opening calls are held. A deadline on the screening date remains timezone-sensitive. No deadline is inferred from a programme's existence. Calendar evidence supports ISO dates and unambiguous written English dates; ambiguous numeric dates remain unresolved. Captures older than 30 days require refresh and prevent an aligned classification.

Ranking sorts the fit classes above in order, then uses explicit criterion weights: met +2, mismatch −4, unknown −1; unknown timing −10 and closed timing −1000. It does not rank by imagined success probability, prestige, awards or unsupported funding amounts. Funding ranges appear only when both numeric bounds and currency are supported by the captured quotation. Next actions identify missing applicant evidence, current timing questions, official-rule checks and supported document requirements; no action is sent or executed.

## Actual official source verification

Primary pages were browsed and fetched over certificate-verified HTTPS on **2026-10-27**. The final live runs retain original raw response bytes, extraction, SHA256, retrieval timestamp, resolved public IP and HTTP status. Those records are under `acceptance_runs/68-product-sellability-20261027/funding-finder/reviewed/`.

| Case | Actual official source | Result on the synthetic applicant record |
|---|---|---|
| Moya SkillLab | [NYDA Grant Programme](https://www.nyda.gov.za/Products-Services/NYDA-Grant-Programme.html) and [TIA funding instruments](https://www.tia.org.za/funding-instruments/) | Both remain unknown: source pages do not establish a current application window, and applicant age/citizenship or technical evidence is missing. |
| Limpopo AgriRobotics | Same NYDA and TIA pages | NYDA records an R&D seed-capital exclusion mismatch. TIA has two supported criterion comparisons, but proof-of-concept evidence, partner route, current round and complete eligibility remain unresolved. |
| South African applicant against UK programme | [National Lottery Community Fund: England](https://www.tnlcommunityfund.org.uk/funding/england) | Explicit geographic mismatch. This is not marketed as a South African opportunity. |

No SA programme is advertised as currently open or eligible. No funding cap was inferred for TIA's Seed Fund from amounts belonging to other programmes on the same multi-programme page. No NYDA lifetime cumulative limit was relabelled as a current application award range. Linked NYDA PDF material and the HTML page can differ on thresholds and procedures; the service does not silently reconcile them into a more generous claim. A funder must resolve the operative rules.

## Fetch and provenance controls

Offline supplied snapshots are the default and are explicitly labelled as supplied, not independently retrieved. A claimed SHA256 must match raw bytes. Source dates cannot be after the screening date. The output directory must be empty, preventing stale customer artifacts from crossing cases. Applicant source hashes and exact quotations are retained separately.

Live fetching requires `fetch_public=True` and an exact URL in `packet.official_url_allowlist`. Only HTTPS port 443 without credentials/fragments is accepted. All DNS results must be public unicast addresses; private, loopback, link-local, multicast and IPv6 transition/translation addresses are refused. The connection pins a validated IP while TLS validates the official hostname, avoiding DNS check/use rebinding. Redirects are refused. Each request has a 15-second connection/socket timeout and a 2 MiB response limit; only HTML/plain-text responses are accepted. Source text is never executed. Spreadsheet formula prefixes are neutralised in CSV text fields.

These controls constrain fetching; they do not prove that a user-declared URL belongs to the named funder. Official-source selection remains accountable research work. Capture dates and hashes establish provenance and integrity, not funder endorsement or semantic truth.

## Verification and remaining authority

Fail-first tests initially failed on the absent module. Additional fail-first cases exposed missing exclusion comparison, written-date parsing, sentence-final numeric evidence and unsupported document-instruction leakage; each was corrected. DNS tests also caught multicast/IPv6 translation addresses before any connection attempt.

```bash
.venv/bin/python -m unittest tests.test_funding_finder_pipeline tests.test_report_pitch_pipeline tests.test_format_core -v
.venv/bin/python scripts/run_funding_finder_acceptance.py --out /new/acceptance/root --fetch-official
```

The final acceptance contains entirely synthetic baseline, adversarial/expired and unseen-applicant cases, plus three actual official-page retrieval cases with synthetic applicants. All produce real documents, pass Format Core checks and retain evidence/next actions. The SA report was visually inspected: two readable pages with an explicit table, source links/hashes, separate unknown/mismatch statements and document requests. It contains no fixture-only claim of current eligibility.

All receipts retain `eligibility_certified=false`, `award_guaranteed=false`, `application_submitted=false`, `externally_sent=false` and `canon_promoted=false`. This is a sellable bounded funding-research and application-readiness service. Submission, funder confirmation, authoritative eligibility decisions and award decisions remain outside its authority. No existing canon, maturity registry or shared native-grade module was changed by this implementation.

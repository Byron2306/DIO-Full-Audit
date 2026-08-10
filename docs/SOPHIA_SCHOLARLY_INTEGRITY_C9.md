# Sophia C9 Scholarly Integrity Desk

## Purpose

C9 turns the existing Sophia commercial section-review pilot into an inspectable scholarly-integrity workflow without weakening Sophia's authorship boundary.

Sophia is not positioned as an AI detector, plagiarism detector, ghostwriter, misconduct adjudicator or publication oracle.

The product thesis is simpler and stronger:

> **Sophia does not detect integrity. She makes scholarly integrity inspectable.**

The review therefore exposes the chain between a manuscript's claims, evidence burden, candidate sources, visible support, warrants, limitations, provenance, revision actions and human decisions.

## Existing engine retained

C9 does not replace the existing Sophia review pipeline.

The existing governed route remains responsible for:

- manuscript parsing;
- deterministic citation/reference audit;
- material-claim selection and claim-type classification;
- governed scholarly retrieval;
- claim-to-source mapping;
- source-quality and entailment signals;
- closed-world Gemini reviewer commentary;
- paragraph and claim anchors;
- Mandos judgment;
- Genesis Article I-XII conformance;
- commentary grounding validation;
- repair/rejection when release checks fail; and
- human review before delivery.

C9 adds a product-facing integrity layer around those artifacts and binds the paid review into Sophia's existing Speculum project-store machinery.

## Product route

```text
manuscript + author consent
        |
        v
existing Sophia review pipeline
        |
        +--> reference audit
        +--> literature discovery leads
        +--> material claim classification
        +--> claim/source mapping
        +--> governed reviewer commentary
        |
        v
C9 SCHOLARLY INTEGRITY LAYER
        |
        +--> scholarly risk register
        +--> source verification queue
        +--> Speculum integrity record
        +--> Authorship Preservation Index
        +--> integrity passport
        |
        v
human reviewer approval
        |
        v
initial review delivery
        |
        v
AUTHOR REVISES IN OWN WORDS
        |
        v
same governed route on revised section
        |
        v
revision integrity report
        |
        v
human reviewer approval
        |
        v
governed revision delivery draft
```

## Ten product artifacts

The launch pilot now exposes ten useful artifacts:

1. **Literature Discovery Map**  
   Governed source leads aligned to the research question. Leads are not automatically treated as support.

2. **Technical Reference Audit**  
   Cited-but-missing, listed-but-uncited, duplicates, DOI/metadata and deterministic style findings.

3. **Claim-to-Source Ledger**  
   Material claims classified by evidence burden and mapped against candidate source spans.

4. **Scholarly Risk Register**  
   Claim/evidence and reference-integrity risks prioritised as review work. These are not findings of misconduct.

5. **Source Verification Queue**  
   Concrete full-text, locator, metadata and evidence-standard checks that still require a human.

6. **Speculum Integrity Record**  
   Sophia's existing hash-chained project-store record containing claim/evidence/warrant/limitation, provenance, unresolved risk, response provenance and revision-lineage fields.

7. **Authorship Preservation Index**  
   The existing transparent Sophia engineering signal is exposed with its native validation boundary. It is **not** a forensic authorship detector and cannot establish whether text was written by a human or a model.

8. **Governed Reviewer Commentary**  
   Document/claim-anchored commentary accepted only when the Gemini reasoned-integrity lane, Mandos, Genesis conformance and closed-world grounding checks pass.

9. **Integrity Passport**  
   Manuscript hash, output hashes, provider/model, grounding state, Mandos/Article state, Speculum record hash and authority boundaries.

10. **Revision Integrity Report**  
    The included revision round compares the reviewed risk state before and after the human author's revision, including newly surfaced high-risk claims.

## Scholarly Risk Register

The risk register deliberately separates risk from misconduct.

A high-risk causal claim paired with a topically relevant source may still be recorded as:

```text
claim type: causal
required evidence: causal inference
candidate source: relevant
support state: background_only
severity: high
human action: narrow the claim, add/replace evidence, or make warrant and limitation explicit
```

This is a stronger integrity outcome than treating retrieval relevance as evidence.

Potential claim support states include:

- `support_ready`
- `partial_support`
- `background_only`
- `does_not_support`
- `unmapped`

Even `support_ready` remains subject to the verification queue. The full source still has to be inspected before the author relies on it.

## Source Verification Queue

Every candidate lead that matters to a claim carries a human verification task. Typical tasks are:

- verify bibliographic metadata against a publisher or scholarly index;
- inspect the full publication;
- locate the exact supporting passage;
- confirm the visible passage meets the claim's evidence standard;
- confirm a page/section locator rather than inventing one; and
- decide whether to narrow, qualify, retain or replace the claim/source relationship.

C9 does not include a machine transition called `verified_support` that bypasses this decision.

## Speculum integration

C9 invokes the actual vendored `SophiaProjectStore` when the preferred Valinor Sophia tree is unavailable.

The commercial manuscript becomes a project-scoped draft version. C9 projects the commercial claim/source ledger into Sophia's claim ledger and records the governed review as an integrity-auditor intervention. It then calls Sophia's native:

```text
export_integrity_record(project_id=...)
```

This exposes existing deeper Sophia objects such as:

- Speculum ledger entries;
- evidence transition;
- claim lineage;
- source-quality snapshot;
- NLI/semantic support;
- unresolved risks and unknowns;
- response provenance;
- revision movement;
- pedagogical event traces; and
- Authorship Preservation Index.

The resulting record is hash-bound and included in the commercial ZIP.

## Authorship boundary

The Authorship Preservation Index is retained because it measures a useful engineering property of the Sophia workflow: whether assistance remains grounded, bounded, provenance-visible and handed back to the human author.

It is **not** an authorship classifier.

The commercial passport therefore states explicitly:

```text
engineering signal only
misconduct finding authority: false
automatic source promotion: false
human author owns final wording: true
```

Sophia must never turn this signal into claims such as:

- "this text was written by AI";
- "this text was written by a human";
- "plagiarism detected"; or
- "academic misconduct proven".

## Included revision round

The previous commercial configuration promised one revision round but did not have a real revision state machine. C9 closes that gap.

After the author receives the initial review and revises the section, the revised manuscript is run through the full governed review route again.

The resulting `REVISION_INTEGRITY_REPORT` records:

- original and revised source SHA-256;
- original and revised open scholarly-risk counts;
- original and revised reference findings;
- deltas;
- newly surfaced high-risk claims; and
- overall movement:
  - `improved`
  - `new_or_shifted_risk`
  - `stable`
  - `mixed`

A lower numerical risk count is not allowed to hide newly introduced high-risk claims.

The comparison is explicitly diagnostic. It does not determine who authored the revision.

## Commercial commands

The existing commercial lane still handles intake, payment and initial job authority.

Example controlled setup:

```bash
python scripts/manage_sophia_commercial.py create --spec request.json --controlled
```

Run the C9 review and integrity enrichment:

```bash
python scripts/run_sophia_scholarly_integrity_c9.py run SOPHIA-JOB-ID
```

Human approval of the initial pack remains on the existing Sophia commercial lane:

```bash
python scripts/manage_sophia_commercial.py approve SOPHIA-JOB-ID --reviewer "Reviewer Name"
python scripts/manage_sophia_commercial.py prepare-delivery SOPHIA-JOB-ID
```

After the author revises the section:

```bash
python scripts/run_sophia_scholarly_integrity_c9.py revision SOPHIA-JOB-ID \
  --document ~/revised-section.docx
```

Approve the governed revision pack:

```bash
python scripts/run_sophia_scholarly_integrity_c9.py approve-revision SOPHIA-JOB-ID \
  --round 1 \
  --reviewer "Reviewer Name"
```

Prepare the revision delivery draft:

```bash
python scripts/prepare_sophia_c9_revision_delivery.py SOPHIA-JOB-ID --round 1
```

The mail intent still passes through DIO's separate mail-approval/release mechanism.

## Future scoped products

C9 keeps the $49 postgraduate section review as the narrow release offer. The same machinery makes two adjacent services credible enough to scope manually:

### Supervisor Integrity Review

A supervisor-facing view could show:

- high-burden claims;
- source-support gaps;
- unresolved warrants/limitations;
- recurring revision risks;
- before/after revision movement; and
- the student's recorded final decisions.

It must not grade the student or replace supervisory judgment.

### Research Integrity Assurance Pack

For a faculty, research unit or project team, Sophia could combine:

- source/provenance audit;
- policy mapping;
- claim/evidence review;
- document/table/figure evidence inspection;
- AI-assistance provenance disclosure;
- release hashes; and
- named human sign-off.

This should be sold as an assurance/audit-support workflow, not an institutional misconduct determination. Formal policy/legal review is required before making institution-specific compliance claims.

## Additional credible future lanes

The existing Sophia architecture also supports future experiments in:

- methods/results claim-burden review, especially causal and statistical claims;
- literature-review provenance audit;
- longitudinal thesis-chapter Speculum records;
- pre-submission integrity passports;
- AI-assistance disclosure records that document what Sophia actually did rather than pretending to detect hidden AI use;
- policy-aware module/assessment assistance boundaries; and
- supervisor-visible revision lineage with author-owned final decisions.

## C9 proof boundary

GitHub CI can prove:

- deterministic risk classification behavior;
- no background-only source promotion;
- source-verification queue fail-safe behavior;
- real vendored SophiaProjectStore integration;
- actual Speculum integrity-record generation;
- authorship-metric boundary propagation;
- revision comparison logic;
- public product wording; and
- service/config coherence.

GitHub CI cannot prove the quality of a live Gemini reviewer encounter or the accuracy of scholarly retrieval against arbitrary real manuscripts.

Before broad promotion, the deployment proof should include at least:

1. one real postgraduate manuscript section;
2. one real reviewer-approved initial pack;
3. human full-text verification of the highest-risk mapped sources;
4. a human-authored revision;
5. the C9 revision integrity report; and
6. a reviewer assessment of whether the pack materially improved the author's revision decisions without replacing authorship.

That is the right commercial proof for Sophia because the value proposition is not "the AI knew the answer." The value proposition is that the scholarly decision became inspectable, bounded and easier for the human to make well.

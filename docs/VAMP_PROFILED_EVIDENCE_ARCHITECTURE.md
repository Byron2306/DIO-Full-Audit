# VAMP Profiled Evidence Architecture

## Product Position

VAMP is an organisation-neutral performance evidence preparation service. It does not rate an employee, recommend an employment action, or treat an unverified email match as proof.

The NWU implementation is now one profile installed on the VAMP core. A second, institution-neutral higher-education profile proves that the product vocabulary, domains, evidence rules and acceptance thresholds can change without rewriting the pipeline.

## Working Route

```text
performance agreement + evidence corpus
  -> institutional profile
  -> objective and review-window normalisation
  -> four-dimensional mapping calibration
  -> accepted / candidate / duplicate / unmapped separation
  -> coverage, declaration and gap analysis
  -> Evidex provenance pack
  -> human review
  -> governed payment and delivery state
```

## Profile Boundary

Profiles in `config/vamp_profiles/` define:

- institutional terminology and performance domains;
- aliases and identifier patterns;
- retrieval stopwords;
- strong and weak evidence cues;
- acceptance thresholds; and
- whether an authoritative rating rubric exists.

The core adapter does not contain NWU KPA meanings. `nwu_academic_v1.json` contains that policy. `university_generic_v1.json` provides a portable starting point for another university.

## Mapping Confidence

Every proposed mapping receives four independent confidence values:

1. Retrieval: how reliably the source was found for the objective and period.
2. Relevance: whether identifiers, meaningful terms and domain signals agree.
3. Provenance: whether the source is traceable and its origin is known.
4. Sufficiency: whether the source supports completion rather than merely mentioning an activity.

Overall confidence is the weakest of the four values. A source is accepted only when all four dimensions meet the active profile thresholds. Everything else remains a review candidate, duplicate, or unmapped source.

## Evidex Contract

VAMP sends accepted evidence to Evidex using immutable objective IDs. Human-readable titles remain display metadata. This prevents similarly worded monthly objectives from being merged or cross-matched by broad keywords.

Evidex then produces the evidence table, provenance ledger, quality report and pack receipt. Raw Outlook authentication state and raw mailbox storage are excluded from the release archive.

## Commercial Gates

The commercial state machine enforces:

- explicit evidence-owner, processing and human-review consent;
- payment verification or an explicit controlled-pilot waiver;
- profile and source validation before intake acceptance;
- human approval before delivery preparation;
- Outlook draft creation rather than automatic sending; and
- no automatic rating.

The DIO Control Deck exposes only the next valid action for each job.

## Private Proof

`VAMP-COMMERCIAL-PRIVATE-001` processed the existing NWU corpus through the commercial route:

- 190 evidence records inspected;
- 171 unique source hashes;
- 116 accepted mappings;
- 24 mappings retained as review candidates;
- 19 duplicates suppressed;
- 35 sources left unmapped;
- 39 of 61 objectives evidence-backed (63.9%);
- 20 explicit no-evidence declarations; and
- 2 unresolved gaps.

The VAMP and Evidex coverage totals agree. The job is held at `snapshot_ready` for operator review.

## Institution-Neutral Proof

`VAMP-GENERIC-UNIVERSITY-PROOF-001` uses `university_generic_v1` and a synthetic Example Metropolitan University corpus with no NWU terminology or real personal data:

- 6 objectives across teaching, research, leadership, engagement and development;
- 5 evidence records;
- 3 accepted mappings;
- 1 weak invitation retained as a review candidate;
- 1 explicit no-evidence declaration; and
- 2 open gaps, including the candidate-only objective.

Evidex generated the downstream provenance pack successfully. This proves that NWU is an installed profile rather than a hard-coded product dependency.

## Adding Another Organisation

1. Obtain the organisation's authorised performance framework and terminology.
2. Create a new profile from `university_generic_v1.json`.
3. Map local domains and aliases without changing core code.
4. Set conservative evidence cues and confidence thresholds.
5. Run a redacted controlled corpus and inspect false positives and false negatives.
6. Approve the profile only after the organisation's authorised reviewer signs off.
7. Keep rating disabled unless an authoritative rubric is supplied, encoded and independently validated.

This same profile mechanism can support universities, NGOs, consultancies, professional-service teams and other evidence-heavy organisations. Each market receives its own terminology and policy profile while sharing one governed evidence engine.

## Commands

```bash
.venv/bin/python scripts/manage_vamp_commercial.py create \
  --spec requests/vamp_commercial_private_validation.json --controlled

.venv/bin/python scripts/manage_vamp_commercial.py run VAMP-COMMERCIAL-PRIVATE-001

.venv/bin/python scripts/manage_vamp_commercial.py approve \
  VAMP-COMMERCIAL-PRIVATE-001 --reviewer "Authorised reviewer"

.venv/bin/python scripts/manage_vamp_commercial.py prepare-delivery \
  VAMP-COMMERCIAL-PRIVATE-001
```

Approval and delivery preparation remain separate actions by design.

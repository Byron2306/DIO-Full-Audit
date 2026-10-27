#!/usr/bin/env python3
"""Run eight held customer-specialist offerings through three honest scenarios.

This is deterministic synthetic engineering evidence, NOT professional sign-off.
No publication, payment, send, external authority or BEAST/Seraph execution is
created by this runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.customer_product_router import run_customer_product


EIGHT_PRODUCTS = (
    'AuditProof', 'QualityProof', 'VendorProof', 'AssuranceRoom',
    'DiligenceRoom', 'DonorProof', 'ImpactProof', 'ProgrammeProof',
)

_SOURCES: dict[str, tuple[str, str, str]] = {
    'AuditProof': (
        'Control AC-17 requires a dated signed access review record for each quarter.',
        'The Q2 review register contains an owner-reported signature dated 2026-10-02.',
        'The source register reports the Q2 control review was signed 19 days late.',
    ),
    'QualityProof': (
        'Quality criterion QC-17 requires retained calibration checks for each inspection period.',
        'The inspection log lists a calibration entry dated 2026-10-02.',
        'The inspection log reports no verified calibration record for one production shift.',
    ),
    'VendorProof': (
        'Supplier rule VD-17 requires a current insurance certificate at onboarding.',
        'The supplier packet includes an insurance certificate recorded as dated 2026-10-02.',
        'The supplier packet reports that its insurance certificate expired before onboarding.',
    ),
    'AssuranceRoom': (
        'Assurance criterion AS-17 requires each reviewed control to link to an evidence record.',
        'The control register lists an evidence record dated 2026-10-02.',
        'The control register states that one supporting evidence record could not be located.',
    ),
    'DiligenceRoom': (
        'Diligence request DD-17 requires a complete beneficial ownership disclosure.',
        'The submitted ownership disclosure records a filing dated 2026-10-02.',
        'The source-reported ownership disclosure omits an identified shareholder.',
    ),
    'DonorProof': (
        'Donor condition DN-17 requires source vouchers for expenditure assertions.',
        'The supplied expenditure register references a voucher dated 2026-10-02.',
        'The expenditure register reports three payment lines without supporting vouchers.',
    ),
    'ImpactProof': (
        'Indicator IM-17 requires baseline and follow-up measurements for an outcome claim.',
        'The monitoring report lists baseline and follow-up entries dated 2026-10-02.',
        'The monitoring report provides a follow-up value but no baseline measurement.',
    ),
    'ProgrammeProof': (
        'Programme criterion PR-17 requires signed attendance evidence for reported delivery.',
        'The programme register lists a session and signature dated 2026-10-02.',
        'The programme report lists a delivered session without a signed attendance register.',
    ),
}

SCENARIOS = ('normal', 'messy', 'adversarial')
DISPOSITIONS = {
    'normal': 'EVIDENCE_RECEIVED_UNVERIFIED',
    'messy': 'EVIDENCE_NOT_SUPPLIED',
    'adversarial': 'SOURCE_REPORTED_CHALLENGE',
}


def build_synthetic_packet(product_name: str, scenario: str) -> dict[str, Any]:
    if product_name not in _SOURCES or scenario not in SCENARIOS:
        raise ValueError('unknown specialist product or qualification scenario')
    criterion, observed, challenged = _SOURCES[product_name]
    source_record = challenged if scenario == 'adversarial' else (
        'The source custodian reports no record was supplied for the stated criterion.'
        if scenario == 'messy' else observed
    )
    packet: dict[str, Any] = {
        'owner_authorized': True,
        'case_id': f'QUAL-{product_name.upper()}-{scenario.upper()}',
        'title': f'{product_name} {scenario} controlled qualification',
        'review_at': '2026-10-27T18:00:00+02:00',
        'sources': [
            {'source_id': 'CRITERION', 'text': criterion},
            {'source_id': 'RECORD', 'text': source_record},
        ],
        'requirements': [{
            'requirement_id': 'R17', 'source_id': 'CRITERION', 'quote': criterion,
            **({'label': 'CERTIFIED FULL COMPLIANCE'} if scenario == 'adversarial' else {}),
        }],
        'evidence': ([{'source_id': 'RECORD', 'quote': source_record, 'supports': ['R17']}]
                     if scenario != 'messy' else []),
        'issues': ([{'source_id': 'RECORD', 'quote': source_record, 'requirement_id': 'R17'}]
                   if scenario == 'adversarial' else []),
    }
    return packet


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_journey(out: Path, product_name: str, scenario: str, result: dict[str, Any], render_pdf: bool) -> dict[str, Any]:
    for artifact in result['artifacts']:
        file = (out / artifact['path']).resolve()
        if not file.is_relative_to(out.resolve()) or not file.is_file() or _sha(file) != artifact['sha256']:
            raise ValueError('generated artifact source custody/hash mismatch')
    worksheet = json.loads((out / 'SPECIALIST_REVIEW_WORKSHEET.json').read_text(encoding='utf-8'))
    row = worksheet['rows'][0]
    expected_evidence = 'NOT_SUPPLIED' if scenario == 'messy' else 'RECEIVED_UNVERIFIED'
    if row['evidence_state'] != expected_evidence:
        raise ValueError(f'evidence state mismatch: {row["evidence_state"]}')
    if row['review_state'] == 'SUPPORTED':
        raise ValueError('synthetic self-reported evidence became professionally supported')
    if scenario == 'adversarial' and row['review_state'] != 'CONTESTED':
        raise ValueError('source-reported challenge did not reach native contested review')
    if (scenario == 'adversarial') != bool(row['source_reported_issues']):
        raise ValueError('source-reported challenge crossed scenario boundary')
    html = next((out / 'customer_delivery').glob('*.html')).read_text(encoding='utf-8')
    if row['requirement_quote'] not in html or 'CERTIFIED FULL COMPLIANCE' in html:
        raise ValueError('missing source quotation or ungrounded certification promoted')
    formats = {p.suffix for p in (out / 'customer_delivery').iterdir() if p.is_file()}
    needed = {'.docx', '.html', '.pdf'} if render_pdf else {'.docx', '.html'}
    if not needed.issubset(formats):
        raise ValueError('required review deliverable channels missing')
    shared = result['shared_production_finish']
    if [s['organ'] for s in shared['organ_steps']] != ['format_core', 'production_studio'] or any(s['state'] != 'PASS' for s in shared['organ_steps']):
        raise ValueError('shared Format Core and Production Studio finishing incomplete')
    if result['release_authorized'] is not False or result['receipt']['professional_approval'] != 'NOT_GRANTED':
        raise ValueError('held professional/release authority boundary changed')
    return {
        'product_name': product_name, 'scenario': scenario, 'status': 'PASS',
        'disposition': DISPOSITIONS[scenario], 'native_review_state': row['review_state'],
        'evidence_state': row['evidence_state'], 'record_count': len(row['record_quotes']),
        'challenge_count': len(row['source_reported_issues']), 'studio_finish_verified': True,
        'artifact_hashes_checked': len(result['artifacts']), 'formats': sorted(formats),
        'release_authorized': False, 'professional_approval': 'NOT_GRANTED',
    }


def run_qualification(
    output_root: Path, *, product_names: tuple[str, ...] = EIGHT_PRODUCTS, render_pdf: bool = True,
) -> dict[str, Any]:
    output_root = Path(output_root).resolve()
    if not product_names or len(set(product_names)) != len(product_names) or any(p not in EIGHT_PRODUCTS for p in product_names):
        raise ValueError('qualification requires unique registered evidence offer names')
    if output_root.exists():
        raise ValueError('qualification output must be a new empty destination; preserve existing evidence')
    output_root.mkdir(parents=True, mode=0o700)
    journeys = []
    refusals = []
    for product_name in product_names:
        slug = product_name.lower()
        for scenario in SCENARIOS:
            out = output_root / slug / scenario
            packet = build_synthetic_packet(product_name, scenario)
            try:
                result = run_customer_product(product_name, packet, out, render_pdf=render_pdf)
                journey = _verify_journey(out, product_name, scenario, result, render_pdf)
            except Exception as exc:
                journey = {'product_name': product_name, 'scenario': scenario, 'status': 'FAIL', 'error': str(exc)}
            journeys.append(journey)
            print(f'{product_name:20} {scenario:12} {journey["status"]}', flush=True)

        bad = build_synthetic_packet(product_name, 'normal')
        bad['sources'][0]['sha256'] = '0' * 64
        refused = False
        error = ''
        tamper_out = output_root / slug / 'tamper_refusal'
        try:
            run_customer_product(product_name, bad, tamper_out, render_pdf=False)
        except ValueError as exc:
            error = str(exc)
            refused = 'hash mismatch' in error and not (tamper_out / 'CUSTOMER_EXECUTION_RECEIPT.json').exists()
        refusals.append({'product_name': product_name, 'status': 'REFUSAL_VERIFIED' if refused else 'FAIL',
                         'diagnostic': error})
        print(f'{product_name:20} tamper       {"REFUSED" if refused else "FAIL"}', flush=True)

    success = sum(r['status'] == 'PASS' for r in journeys)
    refused = sum(r['status'] == 'REFUSAL_VERIFIED' for r in refusals)
    receipt = {
        'schema': 'dio.eight_specialist_qualification.v1',
        'test_data': 'SYNTHETIC',
        'products': list(product_names),
        'target_journeys': len(product_names) * len(SCENARIOS),
        'passed': success,
        'failed': len(journeys) - success,
        'tamper_refusal_target': len(product_names),
        'tamper_refusal_verified': refused,
        'journeys': journeys,
        'tamper_refusals': refusals,
        'professional_acceptance': 'NOT_GRANTED',
        'commercial_validation': 'UNPROVED',
        'release_authorized': False,
        'external_effects': False,
        'beast_crystallization': 'NOT_PROVED_BY_THIS_RUN',
        'seraph_monitoring': 'NOT_PROVED_BY_THIS_RUN',
        'claim_boundary': 'Controlled source and customer-document engineering proof, not independent professional acceptance or a market sale.',
    }
    (output_root / 'EIGHT_SPECIALIST_QUALIFICATION_RECEIPT.json').write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8',
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New evidence root; existing directories are refused')
    parser.add_argument('--no-pdf', action='store_true', help='Exclude local LibreOffice PDF conversion')
    parser.add_argument('--require-all', action='store_true', help='Return nonzero for any failed journey or unverified tamper refusal')
    args = parser.parse_args()
    result = run_qualification(args.output, render_pdf=not args.no_pdf)
    print(f'PASSED={result["passed"]}/{result["target_journeys"]} TAMPER_REFUSALS={result["tamper_refusal_verified"]}/{result["tamper_refusal_target"]}')
    print(f'EVIDENCE_ROOT={args.output.resolve()}')
    if args.require_all and (result['failed'] or result['tamper_refusal_verified'] != result['tamper_refusal_target']):
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

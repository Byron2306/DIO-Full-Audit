"""Source-bound specialist worksheets for eight evidence-preparation offers.

These are reviewer work queues, not automated audit, legal, donor, impact,
assurance, procurement or programme conclusions.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Mapping


# Distinct buyer-task wording and review questions; none convey a verdict.
WORKSHEETS: dict[str, tuple[str, tuple[str, str, str, str], str]] = {
    'AuditProof': (
        'Control-testing exception register',
        ('Control', 'Exact control criterion', 'Source-reported exception / record', 'Auditor next action'),
        'Request signed control execution records',
    ),
    'QualityProof': (
        'Nonconformity and corrective-action triage',
        ('Quality check', 'Exact quality requirement', 'Observed record / deviation', 'CAPA review action'),
        'Check corrective-action ownership',
    ),
    'VendorProof': (
        'Supplier document and expiry review',
        ('Supplier requirement', 'Exact document criterion', 'Submitted record / reported date', 'Procurement review action'),
        'Confirm supplier document authenticity',
    ),
    'AssuranceRoom': (
        'Assurance evidence-coverage worksheet',
        ('Assurance control', 'Exact coverage criterion', 'Supplied evidence / challenge', 'Assurance reviewer action'),
        'Establish independent evidence sufficiency',
    ),
    'DiligenceRoom': (
        'Due-diligence outstanding-request ledger',
        ('Diligence request', 'Exact requested disclosure', 'Submitted record / exception', 'Diligence reviewer action'),
        'Resolve the open diligence question',
    ),
    'DonorProof': (
        'Donor claim and expenditure reconciliation',
        ('Donor requirement', 'Exact reporting criterion', 'Reported evidence / reconciliation gap', 'Donor reviewer action'),
        'Reconcile donor-reported expenditure',
    ),
    'ImpactProof': (
        'Impact indicator provenance worksheet',
        ('Impact indicator', 'Exact indicator criterion', 'Reported observation / timeframe', 'Evaluation reviewer action'),
        'Check baseline and follow-up comparability',
    ),
    'ProgrammeProof': (
        'Programme milestone delivery register',
        ('Programme milestone', 'Exact delivery requirement', 'Delivery record / variance', 'Programme reviewer action'),
        'Reconcile milestone evidence and dates',
    ),
}


def build_specialist_worksheet(
    *,
    product_name: str,
    packet: Mapping[str, Any],
    matrix: list[dict[str, Any]],
    sources: Mapping[str, Any],
    quote_anchor: Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Project real source anchors into one bounded product-specific work queue."""
    section, headers, reviewer_action = WORKSHEETS[product_name]
    requirements = {str(r['requirement_id']): r for r in packet.get('requirements') or []}
    rows = []
    for item in matrix:
        requirement_id = str(item['requirement_key'])
        anchor = quote_anchor(requirements[requirement_id], sources)
        evidence_anchors = [quote_anchor(r, sources) for r in packet.get('evidence') or []
                            if requirement_id in (r.get('supports') or [])]
        issue_anchors = [quote_anchor(r, sources) for r in packet.get('issues') or []
                         if r.get('requirement_id') == requirement_id]
        dates = list(dict.fromkeys(date for a in evidence_anchors
                                   for date in re.findall(r'\b\d{4}-\d{2}-\d{2}\b', a['quote'])))
        record_quotes = [a['quote'] for a in evidence_anchors]
        issue_quotes = [a['quote'] for a in issue_anchors]
        rows.append({
            'requirement_id': requirement_id,
            'requirement_quote': anchor['quote'],
            'requirement_source_id': anchor['source_id'],
            'requirement_source_sha256': anchor['source_sha256'],
            'requirement_source_span': [anchor['start'], anchor['end']],
            'record_quotes': record_quotes,
            'record_sources': [
                {'source_id': a['source_id'], 'sha256': a['source_sha256'], 'span': [a['start'], a['end']]}
                for a in evidence_anchors
            ],
            'source_reported_issues': issue_quotes,
            'reported_dates': dates,
            'reported_dates_verified': False,
            'evidence_state': 'RECEIVED_UNVERIFIED' if evidence_anchors else 'NOT_SUPPLIED',
            'review_state': item['review_state'],
            'record_trust_state': 'captured_untrusted',
            'reviewer_action': reviewer_action,
        })
    worksheet = {
        'schema': 'dio.customer_evidence.specialist_worksheet.v1',
        'product_name': product_name,
        'section': section,
        'table_headers': list(headers),
        'rows': rows,
        'human_review_required': True,
        'professional_approval': 'NOT_GRANTED',
        'release_authorized': False,
        'commercial_validation': 'UNPROVED',
        'claim_boundary': 'Customer-source preparation only; dates, records, exceptions and professional conclusions require independent human verification.',
    }
    display_rows = []
    for row in rows:
        records = '; '.join(row['record_quotes']) if row['record_quotes'] else 'NOT_SUPPLIED'
        issues = '; '.join(row['source_reported_issues'])
        if issues:
            records += ' | Source-reported issue: ' + issues
        display_rows.append([
            row['requirement_id'], row['requirement_quote'], records,
            row['reviewer_action'] + ' (human review; no domain conclusion)',
        ])
    blocks = [
        {'type': 'heading', 'level': 1, 'text': section},
        {'type': 'paragraph', 'text': worksheet['claim_boundary']},
        {'type': 'table', 'headers': list(headers), 'rows': display_rows},
    ]
    return worksheet, blocks

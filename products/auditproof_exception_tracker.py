"""Build an aggregate, source-bound access-review exception handoff."""
from __future__ import annotations
import csv
import io
import re
from typing import Any, Callable, Mapping

NUMBER_WORDS = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}


def _count(value: str) -> int:
    value = value.strip().casefold()
    return int(value) if value.isdigit() else NUMBER_WORDS[value]


def build_exception_tracker(packet: Mapping[str, Any], sources: Mapping[str, Any], quote_anchor: Callable) -> dict[str, Any]:
    source_rows = list(packet.get('sources') or [])
    sample_source = next((row for row in source_rows if re.search(r'\b\d+\s+privileged accounts? were listed\b', str(row.get('text') or ''), re.I)), None)
    issue = next((row for row in packet.get('issues') or [] if re.search(r'account rows? have no recorded reviewer outcome', str(row.get('quote') or ''), re.I)), None)
    policy_requirement = next((row for row in packet.get('requirements') or [] if re.search(r'privileged access.*every quarter', str(row.get('quote') or ''), re.I)), None)
    if not sample_source or not issue or not policy_requirement:
        raise ValueError('AuditProof tracker requires a quarterly access review sample and a source-reported row-level exception')
    text = str(sample_source.get('text') or '')
    listed = re.search(r'\b(\d+)\s+privileged accounts? were listed\b', text, re.I)
    reviewed = re.search(r'\b(\d+)\s+were marked reviewed\b', text, re.I)
    unresolved = re.search(r'\b(\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten)\s+account rows? have no recorded reviewer outcome\b', str(issue.get('quote') or ''), re.I)
    if not listed or not reviewed or not unresolved:
        raise ValueError('AuditProof tracker could not extract the stated population and exception counts')
    total_count, reviewed_count, unresolved_count = _count(listed[1]), _count(reviewed[1]), _count(unresolved[1])
    source_line_anchor = quote_anchor({'source_id': sample_source['source_id'], 'quote': text}, sources)
    issue_anchor = quote_anchor(issue, sources)
    policy_anchor = quote_anchor(policy_requirement, sources)
    count_anchors = []
    for label, match in [('total_listed', listed), ('reviewed', reviewed)]:
        start_char, end_char = match.span(1)
        start = len(text[:start_char].encode('utf-8'))
        end = len(text[:end_char].encode('utf-8'))
        literal = match.group(1)
        count_anchors.append({'field': label, 'literal': literal, 'value': int(literal),
                              'source_id': sample_source['source_id'],
                              'source_sha256': source_line_anchor['source_sha256'],
                              'source_byte_start': start, 'source_byte_end_exclusive': end,
                              'source_ref': f"customer-packet://{sample_source['source_id']}#bytes={start}:{end}"})
    issue_count_start = len(str(issue['quote'])[:unresolved.start(1)].encode('utf-8'))
    issue_count_end = len(str(issue['quote'])[:unresolved.end(1)].encode('utf-8'))
    issue_start = issue_anchor['source_byte_start'] + issue_count_start
    issue_end = issue_anchor['source_byte_start'] + issue_count_end
    issue_count_anchor = {'field': 'no_outcome_rows', 'literal': unresolved.group(1), 'value': unresolved_count,
                          'source_id': issue_anchor['source_id'], 'source_sha256': issue_anchor['source_sha256'],
                          'source_byte_start': issue_start, 'source_byte_end_exclusive': issue_end,
                          'source_ref': f"customer-packet://{issue_anchor['source_id']}#bytes={issue_start}:{issue_end}"}
    date_match = re.search(r'\b\d{4}-\d{2}-\d{2}\b', text)
    review_date = None
    if date_match:
        ds = len(text[:date_match.start()].encode('utf-8'))
        de = len(text[:date_match.end()].encode('utf-8'))
        review_date = {'literal': date_match.group(0), 'source_id': sample_source['source_id'],
                       'source_sha256': source_line_anchor['source_sha256'], 'source_byte_start': ds,
                       'source_byte_end_exclusive': de,
                       'source_ref': f"customer-packet://{sample_source['source_id']}#bytes={ds}:{de}"}
    return {
        'schema': 'dio.auditproof.access_review_exception_tracker.v1',
        'control_requirement': {'quote': policy_anchor['quote'], 'source_id': policy_anchor['source_id'],
                                'source_sha256': policy_anchor['source_sha256'],
                                'source_byte_start': policy_anchor['source_byte_start'],
                                'source_byte_end_exclusive': policy_anchor['source_byte_end_exclusive']},
        'review_sample': {'source_id': source_line_anchor['source_id'], 'source_quote': source_line_anchor['quote'],
                          'source_sha256': source_line_anchor['source_sha256'],
                          'source_byte_start': source_line_anchor['source_byte_start'],
                          'source_byte_end_exclusive': source_line_anchor['source_byte_end_exclusive'],
                          'review_date_candidate': review_date},
        'reported_counts': {'total_listed': total_count, 'marked_reviewed': reviewed_count,
                            'no_outcome_reported': unresolved_count, 'arithmetic_reconciles': total_count == reviewed_count + unresolved_count,
                            'count_anchors': count_anchors + [issue_count_anchor]},
        'exception_group': {'issue_quote': issue_anchor['quote'], 'source_id': issue_anchor['source_id'],
                            'source_sha256': issue_anchor['source_sha256'],
                            'source_byte_start': issue_anchor['source_byte_start'],
                            'source_byte_end_exclusive': issue_anchor['source_byte_end_exclusive'],
                            'account_identifier_state': 'NOT_PRESENT_IN_EXCEPTION_EXCERPT',
                            'fabricated_account_rows_created': False},
        'auditor_request': 'Obtain the original Q3 worksheet or export, identify the specific account rows, record each application-owner outcome, and attach dated closure evidence for any exception.',
        'review_fields': {'original_worksheet_ref': '', 'identified_account_rows': '', 'owner_outcomes': '',
                          'closure_evidence_ref': '', 'closure_evidence_sha256': '', 'auditor_test_result': '',
                          'auditor_name': '', 'reviewed_at_iso8601': '', 'auditor_rationale': ''},
        'claim_boundary': 'Customer-source preparation only. Counts, dates, requirement wording and exceptions remain unverified. Aggregate arithmetic does not establish that any account was reviewed or that a control operated effectively.',
        'human_review_required': True, 'professional_approval': 'NOT_GRANTED', 'release_authorized': False,
    }


def tracker_csv(tracker: Mapping[str, Any]) -> str:
    fields = ['review_date_candidate', 'reported_total_listed', 'reported_marked_reviewed',
              'reported_no_outcome_rows', 'arithmetic_reconciles', 'identified_account_rows',
              'owner_outcomes', 'original_worksheet_ref', 'closure_evidence_ref',
              'closure_evidence_sha256', 'auditor_test_result', 'auditor_name',
              'reviewed_at_iso8601', 'auditor_rationale', 'auditor_request']
    review = tracker['review_fields']
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    counts = tracker['reported_counts']
    writer.writerow({'review_date_candidate': (tracker['review_sample'].get('review_date_candidate') or {}).get('literal', ''),
                     'reported_total_listed': counts['total_listed'], 'reported_marked_reviewed': counts['marked_reviewed'],
                     'reported_no_outcome_rows': counts['no_outcome_reported'], 'arithmetic_reconciles': counts['arithmetic_reconciles'],
                     **review, 'auditor_request': tracker['auditor_request']})
    return buffer.getvalue()

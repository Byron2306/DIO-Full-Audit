"""Source-bound attendance evidence follow-up for ProgrammeProof."""
from __future__ import annotations
import csv
import io
import re
from typing import Any, Callable, Mapping

WORDS = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
         'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}


def _int(value: str) -> int:
    return int(value) if value.isdigit() else WORDS[value.casefold()]


def _anchor(source_id: str, quote: str, sources: Mapping[str, Any], quote_anchor: Callable) -> dict[str, Any]:
    row = quote_anchor({'source_id': source_id, 'quote': quote}, sources)
    return {'source_id': row['source_id'], 'quote': row['quote'], 'source_sha256': row['source_sha256'],
            'source_byte_start': row['source_byte_start'], 'source_byte_end_exclusive': row['source_byte_end_exclusive'],
            'quote_sha256': row['source_quote_sha256'],
            'source_ref': f"customer-packet://{source_id}#bytes={row['source_byte_start']}:{row['source_byte_end_exclusive']}"}


def build_attendance_tracker(packet: Mapping[str, Any], sources: Mapping[str, Any], quote_anchor: Callable) -> dict[str, Any]:
    number = r'(?:\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten)'
    log = next((row for row in packet.get('sources') or [] if re.search(rf'{number} sessions recorded across {number} sites', str(row.get('text') or ''), re.I)), None)
    issue = next((row for row in packet.get('issues') or [] if re.search(r'sessions have no attached attendance sheet', str(row.get('quote') or ''), re.I)), None)
    plan = next((row for row in packet.get('sources') or [] if re.search(rf'targets monthly .* sessions in {number} community sites', str(row.get('text') or ''), re.I)), None)
    if not log or not issue or not plan:
        raise ValueError('ProgrammeProof tracker requires a monthly plan, delivery log and attendance-sheet gap')
    log_text = str(log['text'])
    issue_text = str(issue['quote'])
    logged = re.search(rf'\b({number}) sessions recorded across ({number}) sites in ([A-Za-z]+ \d{{4}})\b', log_text, re.I)
    sheets = re.search(r'attendance sheets were supplied for (\d+) sessions', log_text, re.I)
    missing = re.search(r'\b(\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten) sessions have no attached attendance sheet\b', issue_text, re.I)
    plan_match = re.search(rf'targets monthly ([^.]+?) in ({number}) community sites', str(plan['text'] or ''), re.I)
    if not logged or not sheets or not missing or not plan_match:
        raise ValueError('ProgrammeProof tracker could not extract its declared session counts and scope')
    total, site_count, period = _int(logged.group(1)), _int(logged.group(2)), logged.group(3)
    supplied, missing_count = int(sheets.group(1)), _int(missing.group(1))
    plan_anchor = _anchor(str(plan['source_id']), str(plan['text']), sources, quote_anchor)
    log_anchor = _anchor(str(log['source_id']), log_text, sources, quote_anchor)
    issue_anchor = _anchor(str(issue['source_id']), issue_text, sources, quote_anchor)
    issue_start = len(issue_text[:missing.start(1)].encode('utf-8'))
    issue_end = len(issue_text[:missing.end(1)].encode('utf-8'))
    return {
        'schema': 'dio.programmeproof.attendance_evidence_tracker.v1',
        'review': {'reporting_period': period, 'planned_activity_wording': plan_match.group(1).strip(),
                   'planned_site_count': _int(plan_match.group(2)), 'reported_site_count': site_count,
                   'reported_sessions': total, 'sessions_with_sheets_reported': supplied,
                   'sessions_without_sheets_reported': missing_count,
                   'count_arithmetic_reconciles': total == supplied + missing_count,
                   'participant_reach_count': None,
                   'session_identity_state': 'NOT_PRESENT_IN_SUPPLIED_EXCEPTION',
                   'fabricated_session_rows_created': False,
                   'plan_source': plan_anchor, 'delivery_log_source': log_anchor,
                   'exception_source': issue_anchor,
                   'missing_count_anchor': {'literal': missing.group(1), 'source_id': issue_anchor['source_id'],
                                            'source_sha256': issue_anchor['source_sha256'],
                                            'source_byte_start': issue_anchor['source_byte_start'] + issue_start,
                                            'source_byte_end_exclusive': issue_anchor['source_byte_start'] + issue_end}},
        'request': {'request_id': 'PPR-ATTENDANCE-GAP',
                    'request_text': f"Identify the {missing_count} sessions without attendance sheets and provide their session dates, sites, original attendance records, and source references. Reconcile them to the delivery log before reporting participant reach.",
                    'requested_records': ['Session identifier or exact log row', 'Session date and community site',
                                          'Original attendance sheet or approved attendance record',
                                          'Participant count basis for each session', 'Delivery-log reference'],
                    'review_fields': {'missing_session_ids_and_log_rows': '', 'session_dates_and_sites': '',
                                      'received_attendance_refs': '', 'received_attendance_sha256': '',
                                      'participant_count_reconciliation': '', 'reviewer_decision': '',
                                      'reviewer_name': '', 'reviewed_at_iso8601': '', 'reviewer_rationale': ''}},
        'claim_boundary': 'Customer-source preparation only. Session counts, site coverage and missing-sheet statements remain unverified. Aggregate arithmetic does not establish session delivery or participant reach.',
        'human_review_required': True, 'professional_approval': 'NOT_GRANTED', 'release_authorized': False,
    }


def tracker_csv(tracker: Mapping[str, Any]) -> str:
    review, request = tracker['review'], tracker['request']
    fields = ['request_id', 'reporting_period', 'reported_site_count', 'reported_sessions',
              'sessions_with_sheets_reported', 'sessions_without_sheets_reported',
              'count_arithmetic_reconciles', 'participant_reach_count', 'request_text',
              'requested_records', 'missing_session_ids_and_log_rows', 'session_dates_and_sites',
              'received_attendance_refs', 'received_attendance_sha256', 'participant_count_reconciliation',
              'reviewer_decision', 'reviewer_name', 'reviewed_at_iso8601', 'reviewer_rationale']
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerow({'request_id': request['request_id'], 'reporting_period': review['reporting_period'],
                     'reported_site_count': review['reported_site_count'], 'reported_sessions': review['reported_sessions'],
                     'sessions_with_sheets_reported': review['sessions_with_sheets_reported'],
                     'sessions_without_sheets_reported': review['sessions_without_sheets_reported'],
                     'count_arithmetic_reconciles': review['count_arithmetic_reconciles'],
                     'participant_reach_count': '', 'request_text': request['request_text'],
                     'requested_records': ' | '.join(request['requested_records']), **request['review_fields']})
    return buffer.getvalue()

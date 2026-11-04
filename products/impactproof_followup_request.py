"""Source-bound follow-up request for a reported impact cohort."""
from __future__ import annotations
import csv
import hashlib
import io
import re
from typing import Any, Callable, Mapping

NUMBER_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
                'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}



def _anchor(source_id: str, quote: str, sources: Mapping[str, Any], quote_anchor: Callable) -> dict[str, Any]:
    row = quote_anchor({'source_id': source_id, 'quote': quote}, sources)
    return {'source_id': row['source_id'], 'quote': row['quote'], 'source_sha256': row['source_sha256'],
            'source_byte_start': row['source_byte_start'], 'source_byte_end_exclusive': row['source_byte_end_exclusive'],
            'quote_sha256': row['source_quote_sha256'],
            'source_ref': f"customer-packet://{source_id}#bytes={row['source_byte_start']}:{row['source_byte_end_exclusive']}"}


def build_followup_request(packet: Mapping[str, Any], sources: Mapping[str, Any], quote_anchor: Callable) -> dict[str, Any]:
    framework = next((r for r in packet.get('sources') or [] if re.search(r'sustained employment.*at least six months', str(r.get('text') or ''), re.I)), None)
    observation = next((r for r in packet.get('sources') or [] if re.search(r'\b\d+ participants? reported placed in paid work during \d{4} Q[1-4]\b', str(r.get('text') or ''), re.I)), None)
    exception = next((r for r in packet.get('issues') or [] if re.search(r'no six-month follow-up records were included', str(r.get('quote') or ''), re.I)), None)
    if not framework or not observation or not exception:
        raise ValueError('ImpactProof follow-up request requires a six-month outcome definition, reported cohort and missing follow-up record statement')
    framework_text = str(framework['text'])
    observation_text = str(observation['text'])
    exception_text = str(exception['quote'])
    threshold = re.search(r'\bat least (\d+|one|two|three|four|five|six|seven|eight|nine|ten) months\b', framework_text, re.I)
    cohort = re.search(r'\b(\d+) participants? reported placed in paid work during (\d{4} Q[1-4])\b', observation_text, re.I)
    if not threshold or not cohort:
        raise ValueError('ImpactProof follow-up request could not parse the supplied threshold or cohort count')
    threshold_months = int(threshold.group(1)) if threshold.group(1).isdigit() else NUMBER_WORDS[threshold.group(1).casefold()]
    definition_anchor = _anchor(str(framework['source_id']), framework_text, sources, quote_anchor)
    cohort_anchor = _anchor(str(observation['source_id']), observation_text, sources, quote_anchor)
    exception_anchor = _anchor(str(exception['source_id']), exception_text, sources, quote_anchor)
    return {
        'schema': 'dio.impactproof.followup_evidence_request.v1',
        'cohort_request': {
            'request_id': 'IFR-COHORT-FOLLOWUP', 'reported_cohort_size': int(cohort.group(1)),
            'reported_cohort_period': cohort.group(2).upper(), 'required_followup_duration_months': threshold_months,
            'outcome_definition': definition_anchor,
            'reported_placement': cohort_anchor,
            'followup_gap': exception_anchor,
            'followup_records_state': 'SOURCE_REPORTS_NO_RECORDS_INCLUDED',
            'sustained_outcome_count': None,
            'requested_record_fields': ['Participant record reference', 'Placement/start date',
                                        'Evidence supporting paid-work status', 'Follow-up observation date',
                                        'Work continuity or duration evidence covering the defined period',
                                        'Outcome status and source record reference'],
            'request_fields': {'requested_from': '', 'request_owner': '', 'request_sent_at': '',
                               'received_record_refs': '', 'received_record_sha256': '',
                               'reviewer_comparability_decision': '', 'reviewer_outcome_decision': '',
                               'reviewer_name': '', 'reviewed_at_iso8601': '', 'reviewer_rationale': ''},
            'claim_boundary': 'Reported placement count is an initial cohort statement only. No participant-level follow-up is supplied; the sustained-employment count remains uncalculated.',
        },
        'claim_boundary': 'Source-bound follow-up preparation only. The cohort count, period, outcome definition and missing-record statement are unverified customer-provided content; no impact outcome or programme effectiveness is established.',
        'human_review_required': True, 'professional_approval': 'NOT_GRANTED', 'release_authorized': False,
    }


def request_csv(register: Mapping[str, Any]) -> str:
    row = register['cohort_request']
    form = row['request_fields']
    fields = ['request_id', 'reported_cohort_size', 'reported_cohort_period', 'required_followup_duration_months',
              'followup_records_state', 'sustained_outcome_count', 'requested_record_fields',
              'requested_from', 'request_owner', 'request_sent_at', 'received_record_refs',
              'received_record_sha256', 'reviewer_comparability_decision', 'reviewer_outcome_decision',
              'reviewer_name', 'reviewed_at_iso8601', 'reviewer_rationale']
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerow({'request_id': row['request_id'], 'reported_cohort_size': row['reported_cohort_size'],
                     'reported_cohort_period': row['reported_cohort_period'],
                     'required_followup_duration_months': row['required_followup_duration_months'],
                     'followup_records_state': row['followup_records_state'],
                     'sustained_outcome_count': '',
                     'requested_record_fields': ' | '.join(row['requested_record_fields']), **form})
    return buffer.getvalue()

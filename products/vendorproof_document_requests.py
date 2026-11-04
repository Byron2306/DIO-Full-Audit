"""Source-bound procurement document requests for VendorProof."""
from __future__ import annotations
import csv
import hashlib
import io
import re
from typing import Any, Callable, Mapping

DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
DPA_TERMS = re.compile(r"\b(?:DPA|data[- ]processing addendum|addendum)\b", re.I)
SECURITY_TERMS = re.compile(r"\bsecurity review\b", re.I)


def _anchors(rows: list[Mapping[str, Any]], sources: Mapping[str, Any], quote_anchor: Callable) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for row in rows:
        anchor = quote_anchor(row, sources)
        key = (anchor['source_id'], anchor['source_byte_start'], anchor['source_byte_end_exclusive'])
        if key in seen:
            continue
        seen.add(key)
        result.append({
            'source_id': anchor['source_id'], 'quote': anchor['quote'],
            'source_sha256': anchor['source_sha256'], 'source_byte_start': anchor['source_byte_start'],
            'source_byte_end_exclusive': anchor['source_byte_end_exclusive'],
            'quote_sha256': anchor['source_quote_sha256'],
            'source_ref': f"customer-packet://{anchor['source_id']}#bytes={anchor['source_byte_start']}:{anchor['source_byte_end_exclusive']}",
        })
    return result


def _date_candidates(anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dates = []
    for anchor in anchors:
        text = anchor['quote']
        raw = text.encode('utf-8')
        for match in DATE.finditer(text):
            start = anchor['source_byte_start'] + len(text[:match.start()].encode('utf-8'))
            end = anchor['source_byte_start'] + len(text[:match.end()].encode('utf-8'))
            value = raw[match.start():match.end()]
            dates.append({'literal': match.group(0), 'source_id': anchor['source_id'],
                          'source_sha256': anchor['source_sha256'], 'source_byte_start': start,
                          'source_byte_end_exclusive': end,
                          'literal_sha256': hashlib.sha256(value).hexdigest(),
                          'source_ref': f"customer-packet://{anchor['source_id']}#bytes={start}:{end}"})
    unique = {}
    for row in dates:
        unique[(row['source_id'], row['source_byte_start'], row['source_byte_end_exclusive'])] = row
    return list(unique.values())


def build_document_requests(packet: Mapping[str, Any], sources: Mapping[str, Any], quote_anchor: Callable) -> dict[str, Any]:
    requirements = list(packet.get('requirements') or [])
    evidence = list(packet.get('evidence') or [])
    issues = list(packet.get('issues') or [])
    topics = [
        {'request_id': 'VREQ-DPA', 'topic': 'Executed data-processing addendum', 'pattern': DPA_TERMS,
         'documents': ['Executed addendum file, including its signature/execution page',
                       'Supplier and customer legal-entity names shown on the executed copy',
                       'Execution and effective dates shown in the document'],
         'status': 'SOURCE_REPORTS_NOT_INCLUDED',
         'boundary': 'This request does not decide whether an agreement is legally sufficient or in force.'},
        {'request_id': 'VREQ-SECURITY', 'topic': 'Annual security review', 'pattern': SECURITY_TERMS,
         'documents': ['Underlying security-review report or approved record',
                       'Review scope, completion date, reviewer identity and recorded outcome',
                       'Supplier-confirmed next planned review date; do not infer it from the reported date'],
         'status': 'CUSTOMER_ASSERTION_RECORDED_DATE_UNVERIFIED',
         'boundary': 'This request does not determine review adequacy, supplier security or compliance.'},
    ]
    requests = []
    for topic in topics:
        related_requirements = [row for row in requirements if topic['pattern'].search(str(row.get('quote') or ''))]
        related_evidence = [row for row in evidence if topic['pattern'].search(str(row.get('quote') or ''))]
        related_issues = [row for row in issues if topic['pattern'].search(str(row.get('quote') or ''))]
        if not (related_requirements or related_evidence or related_issues):
            continue
        anchors = _anchors(related_requirements + related_evidence + related_issues, sources, quote_anchor)
        all_dates = _date_candidates(anchors)
        unresolved_fields = {
            'request_owner': '', 'requested_from': '', 'request_sent_at': '',
            'received_document_ref': '', 'received_document_sha256': '',
            'source_authenticity_review': '', 'reviewer_disposition': '',
            'reviewer_name': '', 'reviewed_at_iso8601': '', 'reviewer_rationale': '',
        }
        requests.append({
            'request_id': topic['request_id'], 'document_topic': topic['topic'],
            'request_status': topic['status'], 'documents_to_obtain': topic['documents'],
            'source_anchors': anchors, 'date_candidates': all_dates,
            'request_fields': unresolved_fields, 'review_boundary': topic['boundary'],
        })
    return {
        'schema': 'dio.vendorproof.document_request_register.v1', 'requests': requests,
        'claim_boundary': 'Procurement follow-up preparation only. Source statements and dates remain customer-reported and unverified; requested documents and review outcomes are not supplied by this register.',
        'human_review_required': True, 'professional_approval': 'NOT_GRANTED', 'release_authorized': False,
    }


def requests_csv(register: Mapping[str, Any]) -> str:
    fields = ['request_id', 'document_topic', 'request_status', 'documents_to_obtain',
              'source_anchors', 'date_candidates', 'request_owner', 'requested_from',
              'request_sent_at', 'received_document_ref', 'received_document_sha256',
              'source_authenticity_review', 'reviewer_disposition', 'reviewer_name',
              'reviewed_at_iso8601', 'reviewer_rationale']
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for row in register.get('requests') or []:
        form = row['request_fields']
        writer.writerow({
            'request_id': row['request_id'], 'document_topic': row['document_topic'],
            'request_status': row['request_status'], 'documents_to_obtain': ' | '.join(row['documents_to_obtain']),
            'source_anchors': ' | '.join(anchor['source_ref'] for anchor in row['source_anchors']),
            'date_candidates': ' | '.join(date['literal'] for date in row['date_candidates']),
            **form,
        })
    return buffer.getvalue()

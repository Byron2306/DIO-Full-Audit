"""Source-bound grant expenditure reconciliation handoff."""
from __future__ import annotations
import csv
import hashlib
import io
import re
from typing import Any, Callable, Mapping

AMOUNT = re.compile(r"\b(?P<currency>ZAR|USD|EUR|GBP)\s*(?P<amount>[0-9][0-9,]*(?:\.\d{1,2})?)\b", re.I)
MISSING_INVOICES = re.compile(r"\b(?P<count>\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten)\s+invoice (?:images|copies|documents)\b", re.I)
WORDS = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
         'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}


def _count(value: str) -> int:
    value = value.casefold()
    return int(value) if value.isdigit() else WORDS[value]


def _source_anchor(source_id: str, quote: str, sources: Mapping[str, Any], quote_anchor: Callable) -> dict[str, Any]:
    anchor = quote_anchor({'source_id': source_id, 'quote': quote}, sources)
    return {'source_id': source_id, 'quote': anchor['quote'], 'source_sha256': anchor['source_sha256'],
            'source_byte_start': anchor['source_byte_start'], 'source_byte_end_exclusive': anchor['source_byte_end_exclusive'],
            'quote_sha256': anchor['source_quote_sha256'],
            'source_ref': f"customer-packet://{source_id}#bytes={anchor['source_byte_start']}:{anchor['source_byte_end_exclusive']}"}


def build_expenditure_tracker(packet: Mapping[str, Any], sources: Mapping[str, Any], quote_anchor: Callable) -> dict[str, Any]:
    agreement = next((row for row in packet.get('sources') or [] if re.search(r'restricts funds to', str(row.get('text') or ''), re.I)), None)
    report = next((row for row in packet.get('sources') or [] if re.search(r'\b(?:ZAR|USD|EUR|GBP)\s*[0-9]', str(row.get('text') or ''), re.I)), None)
    exception = next((row for row in packet.get('issues') or [] if MISSING_INVOICES.search(str(row.get('quote') or ''))), None)
    if not agreement or not report or not exception:
        raise ValueError('DonorProof tracker requires a restricted-use agreement, reported expenditure and missing invoice count')
    agreement_text = str(agreement.get('text') or '')
    report_text = str(report.get('text') or '')
    exception_text = str(exception.get('quote') or '')
    amount_match = AMOUNT.search(report_text)
    missing_match = MISSING_INVOICES.search(exception_text)
    if not amount_match or not missing_match:
        raise ValueError('DonorProof tracker could not extract the reported amount or invoice count')
    agreement_anchor = _source_anchor(str(agreement['source_id']), agreement_text, sources, quote_anchor)
    report_anchor = _source_anchor(str(report['source_id']), report_text, sources, quote_anchor)
    exception_anchor = _source_anchor(str(exception['source_id']), exception_text, sources, quote_anchor)
    amount_literal = amount_match.group(0)
    amount_start = len(report_text[:amount_match.start()].encode('utf-8'))
    amount_end = len(report_text[:amount_match.end()].encode('utf-8'))
    missing_start = len(exception_text[:missing_match.start()].encode('utf-8'))
    missing_end = len(exception_text[:missing_match.end()].encode('utf-8'))
    currency = amount_match.group('currency').upper()
    amount_value = float(amount_match.group('amount').replace(',', ''))
    quarter = re.search(r'\bQ[1-4]\s+\d{4}\b', report_text, re.I)
    allowed_use = re.search(r'restricts funds to (.+?)(?:\s+and requires\b|[.;])', agreement_text, re.I)
    if not quarter or not allowed_use:
        raise ValueError('DonorProof tracker needs an explicit reporting period and restricted-use wording')
    restricted_anchor = _source_anchor(str(agreement['source_id']), allowed_use.group(1).strip(), sources, quote_anchor)
    request = {
        'request_id': 'DREQ-INVOICES', 'reported_invoice_image_count': _count(missing_match.group('count')),
        'missing_invoice_count_anchor': {'literal': missing_match.group(0), 'source_id': exception_anchor['source_id'],
                                         'source_sha256': exception_anchor['source_sha256'],
                                         'source_byte_start': exception_anchor['source_byte_start'] + missing_start,
                                         'source_byte_end_exclusive': exception_anchor['source_byte_start'] + missing_end,
                                         'literal_sha256': hashlib.sha256(missing_match.group(0).encode('utf-8')).hexdigest()},
        'reported_expenditure': {'currency': currency, 'amount': amount_value, 'literal': amount_literal,
                                 'period': quarter.group(0).upper(),
                                 'source_id': report_anchor['source_id'], 'source_sha256': report_anchor['source_sha256'],
                                 'source_byte_start': report_anchor['source_byte_start'] + amount_start,
                                 'source_byte_end_exclusive': report_anchor['source_byte_start'] + amount_end,
                                 'literal_sha256': hashlib.sha256(amount_literal.encode('utf-8')).hexdigest()},
        'restricted_use_wording': {'literal': allowed_use.group(1).strip(), **restricted_anchor},
        'source_anchors': [agreement_anchor, report_anchor, exception_anchor],
        'documents_to_obtain': ['All invoice images referenced by the ledger',
                                'Invoice number, supplier, invoice date and itemized description for each invoice',
                                'Amount and currency per invoice; do not infer values from the reported aggregate',
                                'Payment or disbursement reference for each invoice',
                                'Ledger row or account code connecting each invoice to the reported Q3 amount'],
        'invoice_level_amounts_supplied': False,
        'reconciliation_state': 'NOT_COMPUTABLE_MISSING_INVOICE_VALUES',
        'review_fields': {'invoice_ids_and_amounts': '', 'received_invoice_refs': '', 'received_invoice_sha256': '',
                          'payment_evidence_refs': '', 'ledger_reconciliation': '', 'eligible_use_review': '',
                          'reviewer_decision': '', 'reviewer_name': '', 'reviewed_at_iso8601': '', 'reviewer_rationale': ''},
    }
    return {
        'schema': 'dio.donorproof.expenditure_reconciliation_request.v1',
        'requests': [request],
        'claim_boundary': 'Source-bound follow-up only. Grant restriction, reported expenditure and missing-invoice count are customer statements, not independently verified. No expense eligibility or donor compliance decision is made.',
        'human_review_required': True, 'professional_approval': 'NOT_GRANTED', 'release_authorized': False,
    }


def tracker_csv(register: Mapping[str, Any]) -> str:
    fields = ['request_id', 'reported_invoice_image_count', 'reported_expenditure', 'reporting_period',
              'restricted_use_wording', 'reconciliation_state', 'invoice_level_amounts_supplied',
              'documents_to_obtain', 'invoice_ids_and_amounts', 'received_invoice_refs',
              'received_invoice_sha256', 'payment_evidence_refs', 'ledger_reconciliation',
              'eligible_use_review', 'reviewer_decision', 'reviewer_name', 'reviewed_at_iso8601', 'reviewer_rationale']
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for row in register.get('requests') or []:
        review = row['review_fields']
        writer.writerow({'request_id': row['request_id'],
                         'reported_invoice_image_count': row['reported_invoice_image_count'],
                         'reported_expenditure': row['reported_expenditure']['literal'],
                         'reporting_period': row['reported_expenditure']['period'],
                         'restricted_use_wording': row['restricted_use_wording']['literal'],
                         'reconciliation_state': row['reconciliation_state'],
                         'invoice_level_amounts_supplied': row['invoice_level_amounts_supplied'],
                         'documents_to_obtain': ' | '.join(row['documents_to_obtain']), **review})
    return buffer.getvalue()

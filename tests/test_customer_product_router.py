from pathlib import Path

import pytest

from products.customer_product_router import customer_product_catalog, run_customer_product


def test_catalog_retains_all_68_and_distinguishes_missing_customer_contracts():
    catalog = customer_product_catalog()
    assert len(catalog) == 68
    assert len({r['product_name'] for r in catalog}) == 68
    rows = {r['product_name']: r for r in catalog}
    assert rows['Contract Desk']['customer_packet_execution_available'] is True
    assert rows['Report & Pitch Studio']['customer_packet_execution_available'] is True
    assert rows['AuditProof']['customer_packet_execution_available'] is True
    assert rows['Sophia Review']['customer_packet_execution_available'] is False
    assert rows['Sophia Review']['existing_route'] == 'sophia_raw_review'
    assert all(r['commercial_validation'] == 'UNPROVED' for r in catalog)


def test_no_unknown_product_silent_fixture_fallback_or_unapproved_processing(tmp_path: Path):
    with pytest.raises(ValueError, match='unknown product'):
        run_customer_product('Invented Product', {}, tmp_path / 'unknown')
    with pytest.raises(ValueError, match='owner_authorized'):
        run_customer_product('Contract Desk', {}, tmp_path / 'not-authorized')
    with pytest.raises(NotImplementedError, match='customer packet contract'):
        run_customer_product('Sophia Review', {'owner_authorized': True}, tmp_path / 'missing')
    assert not list(tmp_path.iterdir())


def test_actual_customer_packet_reaches_contract_engine_and_shared_receipt(tmp_path: Path):
    packet = {'owner_authorized': True, 'case_id': 'CUSTOMER-1', 'title': 'Actual changed delivery agreement',
              'contract_source_id': 'AGREEMENT', 'sources': [{'source_id': 'AGREEMENT', 'text': '1. Seller must deliver 19 filters by 2027-01-15.'}],
              'review_at': '2026-10-27T09:00:00+02:00'}
    result = run_customer_product('Contract Desk', packet, tmp_path, render_pdf=False)
    assert result['requested_product'] == 'Contract Desk'
    assert result['receipt']['obligation_count'] == 1
    assert result['customer_packet_sha256']
    assert result['human_review_required'] is True
    assert result['release_authorized'] is False
    assert (tmp_path / 'CUSTOMER_EXECUTION_RECEIPT.json').is_file()
    assert '19 filters' in next(tmp_path.glob('customer_delivery/*.html')).read_text()


def test_vamp_customer_api_requires_actual_review_scope_and_native_consents(tmp_path: Path):
    packet={'owner_authorized':True,'case_id':'VAMP-1','title':'Review','sources':[{'source_id':'R','text':'Objective KPA1 requires two research outputs.'}]}
    with pytest.raises(ValueError,match='consents'):
        run_customer_product('VAMP Performance',packet,tmp_path/'no-consent',render_pdf=False)
    packet['consents']={'evidence_owner_authorized':True,'performance_data_processing_approved':True,'human_review_terms_accepted':True}
    with pytest.raises(ValueError,match='review period'):
        run_customer_product('VAMP Performance',packet,tmp_path/'no-dates',render_pdf=False)
    assert not list(tmp_path.iterdir())

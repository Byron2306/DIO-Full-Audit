import io,json,zipfile
from pathlib import Path
from pypdf import PdfReader
from products.obligationfamily import runner

PACK={'product_id':'dio_grantproof','case_id':'QUALITY-001','requirement_or_obligation_ledger':[{'obligation_id':f'OBL-{i}','source':{'locator':f'G-{i}'},'raw_text':f'Applicant must retain supporting record {i}. '+('Documented requirement with source context. '*7),'evaluation':{'status':'NEEDS_REVIEW','status_basis':['Verify against supplied source.']}} for i in range(75)],'evidence_map':[],'missing_evidence_register':[],'contested_state_register':[],'deadline_register':[],'human_review_register':{'fulfilment':'NEEDS_YOU','disclosure':'NEEDS_YOU','external_release':'REFUSE'}}


def test_family_pdf_preserves_last_requirement_and_gate_across_pages():
    raw=runner._pdf('DIO GrantProof',PACK); pdf=PdfReader(io.BytesIO(raw));text='\n'.join(page.extract_text() for page in pdf.pages)
    assert len(pdf.pages)>1
    assert 'G-74' in text and 'record 74' in text
    assert 'External release: REFUSE' in text
    assert 'requirement_or_obligation_ledger' not in text


def test_family_docx_is_customer_report_not_json_dump():
    raw=runner._docx('DIO GrantProof',PACK)
    with zipfile.ZipFile(io.BytesIO(raw)) as z: text=z.read('word/document.xml').decode()
    assert 'Requirements and obligation review' in text and 'G-74' in text
    assert 'requirement_or_obligation_ledger' not in text

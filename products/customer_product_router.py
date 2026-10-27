"""Explicit customer packet contracts over DIO's registered 68-offer portfolio."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
READINESS = {'Corporate Readiness', 'Finance Readiness', 'Finance Readiness Studio', 'POPIA Readiness', 'InvestorProof', 'EntrepreneurProof'}
REPORTS = {'Report & Pitch Studio', 'Article Publication', 'Article Publication Studio'}
CORRESPONDENCE = {'Professional Correspondence', 'Professional Correspondence Studio'}
DOCUMENT_SERVICES = {'Document Studio Edit': 'technical_edit', 'Document Studio Localize': 'translation'}


def customer_product_catalog() -> list[dict[str, Any]]:
    from presence_core.product_binding_registry import build_phase8_binding_registry
    routes = json.loads((ROOT / 'config/professional_evidence_portfolio/v1/routes.json').read_text())['routes']
    result = []
    for binding in build_phase8_binding_registry(ROOT)['bindings']:
        name = binding['product_name']
        native = routes.get(name, {})
        contract = ''
        if name == 'Contract Desk': contract = 'source_contract'
        elif name in READINESS: contract = 'requirements_and_evidence'
        elif name in REPORTS: contract = 'source_report_and_pitch'
        elif name in CORRESPONDENCE: contract = 'source_correspondence'
        elif name == 'FundingFinder': contract = 'applicant_and_official_opportunities'
        elif name == 'Launch Studio': contract = 'source_offer_and_owned_brand_asset'
        elif name == 'Evidex EvidenceOps': contract = 'source_evidence_records'
        elif name == 'VAMP Performance': contract = 'source_objectives_review_period_and_consents'
        elif name in DOCUMENT_SERVICES: contract = 'document_studio_request'
        elif native.get('route') in {'evidence_profile', 'high_risk_profile', 'education_research_profile'}:
            contract = 'requirements_and_evidence_profile'
        result.append({'product_name': name, 'customer_packet_contract': contract or None,
                       'customer_packet_execution_available': bool(contract), 'existing_route': native.get('route'),
                       'existing_journey_route': binding['fulfilment_profile']['route_id'],
                       'quality_state': 'REVIEW_REQUIRED' if contract else 'USE_EXISTING_NATIVE_PROTOCOL',
                       'commercial_validation': 'UNPROVED', 'release_authorized': False})
    return result


def _document(name: str, packet: Mapping[str, Any], out: Path) -> dict[str, Any]:
    from adapters.document_studio.pipeline import run_document_studio
    request = dict(packet)
    request['service'] = DOCUMENT_SERVICES[name]
    source = Path(str(request.get('document_path') or '')).resolve()
    if not source.is_file(): raise ValueError('document_path must identify the supplied customer document')
    actual_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if request.get('source_sha256') and request['source_sha256'] != actual_hash:
        raise ValueError('customer document source hash mismatch')
    request['source_sha256'] = actual_hash
    request['document_path'] = str(source)
    request.setdefault('provider', 'ollama')
    if name == 'Document Studio Localize':
        request.setdefault('target_language', 'Afrikaans')
        request.setdefault('translation_engine', 'lingua')
        request.setdefault('lingua_translation_backend', 'marian_local')
        request.setdefault('lingua_terminology_profile', 'professional_af_v1')
        request.setdefault('automated_language_critic', False)
        request.setdefault('remote_processing_approved', False)
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    request_path = out / 'CUSTOMER_DOCUMENT_REQUEST.json'
    request_path.write_text(json.dumps(request, indent=2, ensure_ascii=False) + '\n')
    job = run_document_studio(request, request_path, out / 'document_studio')
    return json.loads((job / 'DOCUMENT_STUDIO_RECEIPT.json').read_text())


def run_customer_product(product_name: str, packet: Mapping[str, Any], output_dir: str | Path, *, render_pdf: bool = True) -> dict[str, Any]:
    """Prepare a local job from caller-supplied sources without fixture fallback.

    Caller attestation permits local processing only. It grants no professional
    conclusion, publication, send, payment or external release authority.
    """
    row = next((r for r in customer_product_catalog() if r['product_name'] == product_name), None)
    if row is None: raise ValueError(f'unknown product: {product_name}')
    if packet.get('owner_authorized') is not True:
        raise ValueError('owner_authorized=true must explicitly authorize source processing')
    if not row['customer_packet_execution_available']:
        raise NotImplementedError(f'{product_name} has no customer packet contract in this entry point; use its existing native protocol')
    out = Path(output_dir).resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError('customer output directory must be empty')
    if product_name == 'Contract Desk':
        from products.customer_specialist_pathways import build_contract_desk_package
        receipt = build_contract_desk_package(packet, out, render_pdf=render_pdf)
    elif product_name in READINESS:
        from products.customer_specialist_pathways import build_readiness_package
        receipt = build_readiness_package(product_name, packet, out, render_pdf=render_pdf)
    elif product_name in REPORTS:
        from products.report_pitch_pipeline import build_report_pitch_package
        receipt = build_report_pitch_package(packet, out, render_pdf=render_pdf)
    elif product_name in CORRESPONDENCE:
        from products.customer_specialist_pathways import build_correspondence_package
        receipt = build_correspondence_package(packet, out, render_pdf=render_pdf)
    elif product_name == 'FundingFinder':
        from products.funding_finder_pipeline import build_funding_shortlist
        receipt = build_funding_shortlist(packet, out, as_of=packet.get('as_of'), fetch_public=False, render_pdf=render_pdf)
    elif product_name == 'Launch Studio':
        from products.customer_launch_pipeline import build_customer_launch_package
        receipt = build_customer_launch_package(packet, out, render_media=False)
    elif product_name == 'Evidex EvidenceOps':
        from products.customer_specialist_pathways import build_evidex_customer_package
        receipt = build_evidex_customer_package(packet, out, render_pdf=render_pdf)
    elif product_name == 'VAMP Performance':
        from products.customer_specialist_pathways import build_vamp_customer_package
        receipt = build_vamp_customer_package(packet, out, render_pdf=render_pdf)
    elif product_name in DOCUMENT_SERVICES:
        receipt = _document(product_name, packet, out)
    else:
        from products.customer_specialist_pathways import build_evidence_review_package
        receipt = build_evidence_review_package(product_name, packet, out, render_pdf=render_pdf)
    inventory = [{'path': str(p.relative_to(out)), 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                 for p in sorted(out.rglob('*')) if p.is_file()]
    result = {'schema': 'dio.customer_product_execution.v1', 'requested_product': product_name,
              'customer_packet_contract': row['customer_packet_contract'], 'output_dir': str(out),
              'customer_packet_sha256': hashlib.sha256(json.dumps(packet, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest(),
              'receipt': receipt, 'artifacts': inventory, 'human_review_required': True,
              'commercial_validation': 'UNPROVED', 'release_authorized': False, 'external_effects': False}
    (out / 'CUSTOMER_EXECUTION_RECEIPT.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    return result

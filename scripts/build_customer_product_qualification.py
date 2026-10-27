#!/usr/bin/env python3
"""Consolidate historical execution evidence and current product qualification.

This reads existing runs; it neither executes products nor grants acceptance.
The HTML contains summary information and local artifact links, never source
excerpts or private signing records. Detailed historical findings stay in JSON.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from products.customer_product_router import customer_product_catalog

OUTPUT = ROOT / 'acceptance_runs/68-product-sellability-20261027'
BASELINE = ROOT / 'acceptance_runs/68-product-integration-20261027/68_PRODUCT_EXECUTION_QUALITY_AUDIT.json'
AUDIT = ROOT / 'docs/audits/2026-10-27-sellable-product-pathways.md'
RUN_RECEIPT = 'PROFESSIONAL_EVIDENCE_53_X3_RECEIPT.json'

# Aliases share one service capability and the same explicitly identified
# evidence. A Studio name does not create another independent acceptance.
CAPABILITIES = {
    'report_and_pitch': {
        'offers': ['Report & Pitch Studio'],
        'root': 'report-pitch/reviewed-final',
        'service': 'Source-based decision brief and editable presentation',
        'limit': 'Interpretation, recommendations and presentation fit require review; the deck is a restrained evidence briefing.',
    },
    'article_preparation': {
        'offers': ['Article Publication', 'Article Publication Studio'],
        'root': 'report-pitch/reviewed-final',
        'service': 'Attributed article preparation from supplied sources',
        'limit': 'Editorial quality, usage rights and citation authenticity require review; journal acceptance is unproved.',
    },
    'professional_correspondence': {
        'offers': ['Professional Correspondence', 'Professional Correspondence Studio'],
        'root': 'customer-pathways-delivery/correspondence',
        'service': 'Factual records-request or reconciliation letter',
        'limit': 'The sender reviews facts, tone, position and commitments; sending authority is separate.',
    },
    'contract_review_preparation': {
        'offers': ['Contract Desk'],
        'root': 'customer-pathways-delivery/contract',
        'service': 'Clause and obligation register with reviewer questions',
        'limit': 'The contract owner or legal reviewer confirms meaning, triggers and deadlines; enforceability is not determined.',
    },
    'finance_readiness_preparation': {
        'offers': ['Finance Readiness', 'Finance Readiness Studio'],
        'root': 'customer-pathways-delivery/readiness',
        'service': 'Document gap pack and transparent financial calculations',
        'limit': 'An accountant or lender checks requirements, source records and conclusions; no lending or valuation decision is made.',
    },
    'funding_research': {
        'offers': ['FundingFinder'],
        'root': 'funding-finder/reviewed',
        'service': 'Dated opportunity shortlist and application-readiness questions',
        'limit': 'Confirm live availability and full rules with the funder; synthetic applicant examples do not certify eligibility.',
    },
    'launch_kit_preparation': {
        'offers': ['Launch Studio'],
        'root': 'launch-reviewed',
        'service': 'Source-bound channel assets and owned-brand launch kit',
        'limit': 'Brand, claims, rights, destination and release owners require review; no advertising spend or publication is authorized by qualification.',
    },
    'evidence_reconciliation_preparation': {
        'offers': ['Evidex EvidenceOps'],
        'root': 'customer-pathways-delivery/evidex',
        'service': 'Claim-to-record organization and reconciliation preparation',
        'limit': 'Obtain underlying dated records and establish population/period comparability; reported quantities are not verified delivery.',
    },
    'performance_coverage_preparation': {
        'offers': ['VAMP Performance'],
        'root': 'vamp-quality/customer-release-candidate',
        'service': 'Performance evidence coverage preparation',
        'limit': 'Confirm scope, objective mapping and underlying outputs; event dates and achievement sufficiency are unverified. No employee rating or promotion/CPD decision.',
    },
}

RUN_GROUPS = {
    'sophia_held_diagnostic': 'sophia-recovery/journeys-bounded-repair',
    'afrikaans_packaging': 'lingua-afrikaans/canonical-profiled',
    'vamp_evidex': 'vamp-evidex-final',
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def artifact(path: Path, *, declared_sha256: str | None = None) -> dict:
    path = path.resolve()
    result = {'path': str(path.relative_to(ROOT)), 'exists': path.is_file()}
    if path.is_file():
        result.update(bytes=path.stat().st_size, sha256=digest_file(path))
    if declared_sha256:
        result.update(declared_sha256=declared_sha256,
                      declared_hash_matches=result.get('sha256') == declared_sha256.removeprefix('sha256:'))
    return result


def capability_files(capability_id: str, config: dict) -> list[Path]:
    directory = OUTPUT / config['root']
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    files = sorted(path for path in directory.rglob('*') if path.is_file())
    # Preserve the shared source/custody files, but show only the relevant
    # article/report surfaces for the two capabilities sharing this engine.
    if capability_id in {'report_and_pitch', 'article_preparation'}:
        excluded = {'article'} if capability_id == 'report_and_pitch' else {'report', 'pitch', 'proof'}
        files = [path for path in files if not excluded.intersection(path.relative_to(directory).parts)]
    return files


def build_qualification() -> dict:
    baseline = read_json(BASELINE)
    catalog = customer_product_catalog()
    historical = {row['name']: row for row in baseline['products']}
    if len(historical) != 68 or {row['product_name'] for row in catalog} != set(historical):
        raise ValueError('current catalog and historical 68-offer inventory differ')
    pilot_map = {name: key for key, config in CAPABILITIES.items() for name in config['offers']}
    if len(pilot_map) != 12 or len(CAPABILITIES) != 9:
        raise ValueError('pilot qualification must retain twelve names and nine capabilities')

    evidence_index = {}

    def register(path: Path, declared_sha256=None) -> str:
        value = artifact(path, declared_sha256=declared_sha256)
        previous = evidence_index.get(value['path'], {})
        evidence_index[value['path']] = {**previous, **value}
        return value['path']

    baseline_ref, audit_ref = register(BASELINE), register(AUDIT)
    for path in [ROOT / 'products/customer_product_router.py', ROOT / 'products/customer_specialist_pathways.py',
                 ROOT / 'config/professional_evidence_portfolio/v1/routes.json', Path(__file__)]:
        register(path)
    focused_log = OUTPUT / 'FOCUSED_FINAL_TESTS.log'
    if focused_log.is_file():
        register(focused_log)

    fresh_by_offer, run_groups = {}, {}
    for group_id, relative in RUN_GROUPS.items():
        receipt_path = OUTPUT / relative / RUN_RECEIPT
        receipt = read_json(receipt_path)
        receipt_ref = register(receipt_path)
        run_groups[group_id] = {
            'source': receipt_ref, 'generated_at': receipt.get('generated_at'),
            'journey_count': receipt['journey_count'],
            'verified_journey_count': receipt['verified_journey_count'],
            'refused_journey_count': receipt['refused_journey_count'],
            'boundary': 'Mechanical source/custody and held-output execution evidence; no independent professional acceptance.',
        }
        for name, item in receipt['by_incarnation'].items():
            fresh_by_offer[name] = {
                'evidence_group': group_id, 'receipt': receipt_ref,
                'executed_at': receipt.get('generated_at'),
                'verified_count': item['verified_count'], 'variant_count': item['variant_count'],
                'all_variants_verified': item['all_variants_verified'],
                'variants': item['variants'],
            }

    capabilities = {}
    for key, config in CAPABILITIES.items():
        files = capability_files(key, config)
        refs = [register(path) for path in files]
        customer_surfaces = [str(path.relative_to(ROOT)) for path in files
                             if path.suffix.lower() in {'.pdf', '.docx', '.pptx', '.xlsx'}
                             and ('customer_delivery' in path.parts or 'report' in path.parts
                                  or 'pitch' in path.parts or 'article' in path.parts)]
        if key == 'launch_kit_preparation':
            customer_surfaces = [str(path.relative_to(ROOT)) for path in files
                                 if path.name == 'landing.html' or path.suffix.lower() == '.png' and 'assets' in path.parts]
        if not customer_surfaces:
            raise ValueError(f'no actual customer surface for pilot capability: {key}')
        capabilities[key] = {**config, 'assessment': 'OPERATOR_ASSESSED_BOUNDED_PAID_PILOT_CANDIDATE',
                             'example_context': 'Controlled/synthetic examples, not independent customer acceptance.',
                             'artifact_refs': refs, 'customer_deliverable_refs': customer_surfaces,
                             'independent_professional_signoff': False, 'commercial_validation': 'UNPROVED'}

    rows = []
    for catalog_row in sorted(catalog, key=lambda row: row['product_name']):
        name = catalog_row['product_name']
        old = historical[name]
        # Keep original findings, statuses and timestamps verbatim. Current
        # observations are an overlay, never a rewrite of the baseline audit.
        historical_refs = [register(ROOT / value['path'], value.get('sha256')) for value in old.get('artifacts', [])]
        current = fresh_by_offer.get(name)
        key = pilot_map.get(name)
        limits = [str(old.get('known_capability_limits') or 'Historical quality limits remain applicable until specifically superseded.')]
        disposition = 'HISTORICAL_ASSESSMENT_RETAINED_NOT_FRESHLY_RERUN'
        changes = []
        if current:
            disposition = 'CURRENT_HELD_EXECUTION_VERIFIED' if current['all_variants_verified'] else 'CURRENT_INPUT_GAP_REFUSED'
        if name.startswith('Sophia '):
            changes.append('Current held diagnostic preparation replaces the earlier setup block; strict complete constitutional approval is not established.')
            limits = ['Source-grounded engineering drafts require academic review. Tutor prepares practice; completed teaching or learning gains are not proved.']
        if name == 'Document Studio Localize':
            changes.append('Current three-variant local MT packaging execution supersedes the earlier execution state.')
            limits = ['Actual Afrikaans review found semantic and grammatical faults; proficient language approval is pending. Excluded from the twelve pilot candidates.']
        if name in {'PromotionProof', 'CPDProof'}:
            changes.append('Current three variants refuse missing actual review dates; earlier passes relied on invented scope and do not establish current execution.')
            limits = ['Supply explicit actual review dates and appropriate underlying evidence before rerun. No promotion or CPD approval.']
        if key:
            disposition = 'BOUNDED_PAID_PILOT_CANDIDATE_HUMAN_REVIEW_REQUIRED'
            limits = [capabilities[key]['limit']]
            changes.append('Source-driven customer preparation artifacts supplement the historical fixture assessment; operator pilot qualification is provisional.')
            if name in {'VAMP Performance', 'Evidex EvidenceOps'}:
                changes.append('Current native execution and customer source-record deliverables are retained separately from historical runs.')
        if name == 'HOMS Exam Studio':
            limits.append('Assessment reasoning quality remains an unresolved qualification gap.')
        rows.append({
            'name': name, 'product_id': old.get('product_id'), 'suite': old.get('suite'),
            'catalog_contract': catalog_row, 'historical_baseline': old,
            'historical_artifact_refs': historical_refs,
            'current_execution_override': current,
            'canonical_execution_freshly_rerun': current is not None,
            'customer_preparation_examples_current': key is not None,
            'current_disposition': disposition, 'current_changes': changes,
            'pilot_candidate': key is not None, 'distinct_capability_id': key,
            'shared_capability_offer_names': capabilities[key]['offers'] if key else [],
            'current_artifact_refs': capabilities[key]['artifact_refs'] if key else [],
            'customer_deliverable_refs': capabilities[key]['customer_deliverable_refs'] if key else [],
            'quality_limits': limits, 'independent_professional_signoff': False,
            'buyer_acceptance': 'NOT_ESTABLISHED', 'commercial_validation': 'UNPROVED',
            'qualification_grants_release_authority': False,
        })

    return {
        'schema': 'dio.customer_product_qualification.v1',
        'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'evidence_as_of': '2026-10-27',
        'source_snapshot_basis': 'Existing historical audit plus the explicitly named current acceptance run directories; this generator does not rerun products.',
        'summary': {
            'offer_count': len(rows), 'operator_assessed_pilot_named_offers': len(pilot_map),
            'distinct_pilot_capabilities': len(capabilities),
            'customer_packet_contract_count': sum(bool(row['customer_packet_execution_available']) for row in catalog),
            'offers_retaining_existing_native_protocol': sum(not row['customer_packet_execution_available'] for row in catalog),
            'independent_professional_signoffs': 0, 'independent_professional_signoff_denominator': 68,
            'current_native_canonical_extensions_verified': baseline['extension_studio_summary']['current_workspace_extensions_verified'],
            'native_canonical_extension_denominator': baseline['extension_count'],
            'fresh_canonical_named_offers': len(fresh_by_offer),
            'historical_canonical_execution_retained_named_offers': len(rows) - len(fresh_by_offer),
            'current_disposition_counts': dict(Counter(row['current_disposition'] for row in rows)),
        },
        'qualification_basis': {
            'kind': 'Provisional operator assessment for a bounded professionally delivered paid pilot with human review.',
            'assessment_source': audit_ref, 'historical_baseline_source': baseline_ref,
            'named_offer_aliases_count_separately': True,
            'shared_capabilities_do_not_multiply_independent_evidence': True,
            'professional_acceptance': 'NOT_ESTABLISHED', 'buyer_willingness_to_pay': 'UNPROVED',
            'all_68_fresh_execution_claimed': False, 'full_repository_suite_green_claimed': False,
            'native_extension_canonical_proof_recovered_claimed': False,
            'publication_or_professional_authority_created': False,
        },
        'current_execution_evidence_groups': run_groups,
        'capabilities': capabilities, 'products': rows,
        'evidence_artifacts': sorted(evidence_index.values(), key=lambda value: value['path']),
        'remaining_gaps': [
            'Independent expert and customer acceptance of the pilot examples; willingness to pay remains unproved.',
            'Proficient Afrikaans language approval remains pending despite successful packaging.',
            'HOMS assessment reasoning quality remains unresolved.',
            'Current native extension canonical/commercial identity proof remains 0/11.',
            'PromotionProof and CPDProof require actual review dates before their refused variants can run.',
            'The full repository suite is not green; focused verification does not resolve all historical failures.',
        ],
    }


def build_html(report: dict) -> str:
    e = lambda value: html.escape(str(value), quote=True)

    def link(ref: str, label: str) -> str:
        relative = os.path.relpath(ROOT / ref, OUTPUT)
        return f'<a href="{e(quote(relative, safe="/.-_"))}">{e(label)}</a>'

    rows = []
    for row in report['products']:
        current = row['current_execution_override']
        fresh = f"Current canonical: {current['verified_count']}/{current['variant_count']} variants verified" if current else 'Canonical execution: historical record retained; no fresh rerun claim'
        if current and not current['all_variants_verified']:
            fresh += ' — missing review dates refused'
        evidence = []
        if current:
            evidence.append(link(current['receipt'], 'Current execution receipt'))
        # Deliberately link only public-facing customer surfaces here. Raw
        # sources and private signing records never enter the HTML report.
        pdfs = [ref for ref in row['customer_deliverable_refs'] if ref.endswith('.pdf')]
        examples = pdfs[:2] or row['customer_deliverable_refs'][:2]
        evidence.extend(link(ref, f'Example {index + 1}') for index, ref in enumerate(examples))
        if row['pilot_candidate']:
            label = 'Pilot candidate · review required'
        elif current and not current['all_variants_verified']:
            label = 'Blocked: actual dates required'
        elif current:
            label = 'Held preparation · further quality review'
        else:
            label = 'Historical qualification retained'
        contract = row['catalog_contract']['customer_packet_contract'] or 'Existing native protocol'
        historical = row['historical_baseline']
        historical_text = f"Historical grade: {historical['quality_status']}. {len(historical.get('findings', []))} original findings retained in the JSON ledger."
        details = ''.join(f'<p>{e(change)}</p>' for change in row['current_changes'])
        details += '<p>' + e(historical_text) + '</p>'
        evidence_html = ' · '.join(evidence) or 'Historical source references retained in JSON'
        search = ' '.join([row['name'], row['suite'] or '', label, contract]).casefold()
        rows.append(f'<tr data-search="{e(search)}" data-pilot="{str(row["pilot_candidate"]).lower()}"><th scope="row">{e(row["name"])}<small>{e(row["suite"])}</small></th><td><strong>{e(label)}</strong><p>{e(fresh)}</p><details><summary>Assessment history</summary>{details}</details></td><td>{e(contract)}</td><td>{"".join("<p>" + e(limit) + "</p>" for limit in row["quality_limits"])}</td><td>{evidence_html}</td></tr>')

    summary = report['summary']
    cards = ''.join(f'<div class="stat"><strong>{e(value)}</strong><span>{e(label)}</span></div>' for value, label in [
        (f"{summary['operator_assessed_pilot_named_offers']}/68", 'named pilot candidates'),
        (summary['distinct_pilot_capabilities'], 'distinct pilot capabilities'),
        (summary['customer_packet_contract_count'], 'customer packet contracts'),
        ('0/68', 'independent professional sign-offs'), ('0/11', 'current native canonical extension proofs')])
    groups = ''.join(f'<li>{e(key.replace("_", " "))}: {value["verified_journey_count"]}/{value["journey_count"]} journeys verified; {value["refused_journey_count"]} refused. {link(value["source"], "Receipt")}</li>' for key, value in report['current_execution_evidence_groups'].items())
    gaps = ''.join(f'<li>{e(gap)}</li>' for gap in report['remaining_gaps'])
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DIO · 68-product qualification</title>
<style>body{{margin:0;background:#f5f4ef;color:#182b2a;font:16px/1.55 system-ui,sans-serif}}main{{max-width:1450px;margin:auto;padding:40px 28px}}h1{{font-size:clamp(2rem,4vw,3.5rem);line-height:1.1;max-width:950px}}h2{{margin-top:2.2rem}}a{{color:#095e70}}.eyebrow{{font-size:.8rem;letter-spacing:.1em;text-transform:uppercase}}.intro{{max-width:980px;font-size:1.1rem}}.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:14px;margin:28px 0}}.stat{{background:white;padding:20px;border:1px solid #cbd4ce;border-top:4px solid #21675e}}.stat strong{{display:block;font-size:2rem}}.stat span{{display:block;font-size:.88rem}}.note{{max-width:1000px;border-left:4px solid #a66a27;padding:12px 18px;background:#fff7e8}}label{{display:inline-block;margin:8px 18px 15px 0}}input[type=search]{{display:block;min-width:260px;max-width:100%;padding:11px;border:1px solid #839b95;font:inherit}}input:focus-visible,a:focus-visible,summary:focus-visible{{outline:3px solid #a66a27;outline-offset:3px}}.scroll{{overflow:auto;background:white}}table{{border-collapse:collapse;width:100%;min-width:1050px}}th,td{{padding:17px 14px;vertical-align:top;border-bottom:1px solid #ccd5cf;text-align:left}}thead th{{background:#163f3b;color:white;font-size:.85rem}}tbody th{{width:17%}}td{{font-size:.9rem}}td:nth-child(2){{width:25%}}td:nth-child(4){{width:27%}}small{{display:block;font-weight:400;color:#546963;margin-top:8px}}p{{margin:.4rem 0 .9rem}}details{{margin-top:12px}}summary{{cursor:pointer}}footer{{margin-top:28px;color:#52655e;font-size:.9rem}}[hidden]{{display:none!important}}@media(max-width:600px){{main{{padding:25px 16px}}.stats{{grid-template-columns:repeat(2,1fr)}}.stat{{padding:13px}}}}</style></head>
<body><main><p class="eyebrow">DIO · evidence as of {e(report['evidence_as_of'])}</p><h1>68 offers. Twelve bounded pilot candidates.</h1>
<p class="intro">The current operator assessment identifies twelve named offers across nine services for a professionally delivered paid pilot with human review. Buyer acceptance, independent professional sign-off and willingness to pay remain unproved.</p>
<div class="stats">{cards}</div><p class="note">A source-driven preparation API and a passing execution receipt establish useful preparation and traceability. They do not establish professional approval. Studio aliases share evidence. The historical 68-product audit is retained; this report does not claim every product was freshly rerun.</p>
<p>{link(report['qualification_basis']['assessment_source'], 'Qualification audit')} · {link(report['qualification_basis']['historical_baseline_source'], 'Historical baseline')} · <a href="68_PRODUCT_QUALIFICATION.json">Full JSON ledger and SHA-256 evidence inventory</a></p>
<h2>Current execution evidence</h2><ul>{groups}</ul><p>{summary['fresh_canonical_named_offers']} named offers have explicit current canonical overrides; {summary['historical_canonical_execution_retained_named_offers']} retain their historical canonical execution record. Pilot preparation examples are recorded separately. Refusal for missing actual review dates is retained as an input gap.</p>
<h2>Offer qualification</h2><label>Find an offer<input id="search" type="search" placeholder="Name, suite or contract"></label><label><input id="pilots" type="checkbox"> Show twelve pilot names only</label><p id="count" aria-live="polite">68 offers shown</p>
<div class="scroll" tabindex="0" role="region" aria-label="Scrollable offer qualification table"><table><thead><tr><th scope="col">Offer</th><th scope="col">Current assessment</th><th scope="col">Customer input contract</th><th scope="col">Quality limits and review</th><th scope="col">Evidence</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<h2>Remaining qualification gaps</h2><ul>{gaps}</ul><footer>Built {e(report['generated_at'])}. Hashes record the bytes read by the generator. Missing historical files and changed declared hashes remain explicit in the JSON inventory. No private source excerpts or signing records are embedded in this page.</footer></main>
<script>const search=document.getElementById('search'),pilots=document.getElementById('pilots'),rows=[...document.querySelectorAll('tbody tr')];function filter(){{let n=0;for(const row of rows){{row.hidden=!row.dataset.search.includes(search.value.toLowerCase())||(pilots.checked&&row.dataset.pilot!=='true');if(!row.hidden)n++;}}document.getElementById('count').textContent=n+' offers shown';}}search.addEventListener('input',filter);pilots.addEventListener('change',filter);</script></body></html>'''


def main() -> int:
    report = build_qualification()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / '68_PRODUCT_QUALIFICATION.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (OUTPUT / 'index.html').write_text(build_html(report), encoding='utf-8')
    print(json.dumps({'summary': report['summary'], 'evidence_artifact_count': len(report['evidence_artifacts']),
                      'missing_evidence_files': sum(not row['exists'] for row in report['evidence_artifacts']),
                      'declared_hash_mismatches': sum(row.get('declared_hash_matches') is False for row in report['evidence_artifacts'])}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

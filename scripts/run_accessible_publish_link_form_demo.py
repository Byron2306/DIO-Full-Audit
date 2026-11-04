#!/usr/bin/env python3
"""Exercise held link and form interaction review without external effects."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / 'acceptance_runs/68-product-sellability-20261027/ACCESSIBLE_PUBLISH_LINK_FORM_DEMO_20261102_V1'
EVIDENCE = OUT.parent / 'ACCESSIBLE_PUBLISH_LINK_FORM_DEMO_20261102_V1.json'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f'output directory must be new or empty: {OUT}')
    source = '''<!doctype html>
<html lang="en-ZA"><head><meta charset="utf-8"><title>Interaction QA</title></head>
<body><main><h1>Interaction QA</h1>
<p><a id="local-link" href="#details">Show local details</a></p>
<p><a id="external-link" href="https://external.invalid/path?token=must-not-appear">Open approved destination</a></p>
<section id="details" hidden><h2>Details</h2><p>Details are revealed by the local link.</p></section>
<form id="contact-form" action="/submit?token=must-not-appear" method="post">
<label for="contact-name">Contact name</label><input id="contact-name" name="contact_name" value="Sample reviewer">
<button type="submit">Save review</button></form><p id="status" aria-live="polite">Not submitted</p>
<script>
document.querySelector('#local-link').addEventListener('click',event=>{event.preventDefault();document.querySelector('#details').hidden=false;});
document.querySelector('#contact-form').addEventListener('submit',event=>{event.preventDefault();document.querySelector('#status').textContent='Review saved locally';});
</script></main></body></html>'''
    packet = {'owner_authorized': True, 'case_id': 'SYNTHETIC-ACCESSIBLE-PUBLISH-LINK-FORM',
        'title': 'Accessible Publish link and form interaction review', 'document_title': 'Interaction QA',
        'primary_language': 'en-ZA', 'source_html': source, 'image_descriptions': {},
        'decorative_images': [], 'controlled_synthetic_demo': True}
    from products.customer_product_router import run_customer_product

    execution = run_customer_product('Accessible Publish', packet, OUT, render_pdf=False)
    receipt = json.loads((OUT / 'ACCESSIBLE_PUBLISH_RECEIPT.json').read_text())
    review = json.loads((OUT / 'ACCESSIBILITY_REVIEW.json').read_text())
    browser = review['rendered_browser_review']
    links = browser.get('scripted_link_interaction_reviews') or []
    forms = browser.get('scripted_form_submission_reviews') or []
    if (browser.get('scripted_runtime_state') != 'SCRIPTED_POSTLOAD_DOM_INSPECTED'
            or browser.get('scripted_link_interaction_count', 0) < 2
            or browser.get('scripted_form_submission_attempt_count', 0) < 1
            or not any(row.get('text_changed') for row in links if row.get('href_class') == 'same_document_anchor')
            or not all(row.get('native_navigation_prevented') is True for row in links if row.get('state') == 'CLICKED_NATIVE_NAVIGATION_BLOCKED')
            or not any(row.get('submit_event_observed') and row.get('prevented_by_page') for row in forms)
            or not browser.get('native_form_submission_blocked')
            or browser.get('scripted_page_error_count') != 0
            or 'must-not-appear' in (OUT / 'RENDERED_ACCESSIBILITY_REVIEW.json').read_text()
            or receipt.get('release_authorized') is not False or receipt.get('external_publication') is not False
            or receipt.get('conformance_claim') != 'NONE'
            or execution.get('external_effects') is not False):
        raise ValueError('Accessible Publish link/form interaction route failed behavior or held-boundary checks')
    artifacts = []
    for row in execution.get('artifacts') or []:
        path = OUT / row['path']
        if not path.is_file() or path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError(f'Accessible Publish artifact inventory mismatch: {row["path"]}')
        artifacts.append({'path': row['path'], 'bytes': row['bytes'], 'sha256': row['sha256']})
    evidence = {'schema': 'dio.accessible_publish.link_form_execution_evidence.v1',
        'product': 'Accessible Publish', 'route': OUT.relative_to(ROOT).as_posix(),
        'scripted_runtime_state': browser.get('scripted_runtime_state'),
        'link_interaction_count': browser.get('scripted_link_interaction_count'),
        'form_submission_attempt_count': browser.get('scripted_form_submission_attempt_count'),
        'form_submission_event_count': browser.get('scripted_form_submission_event_count'),
        'navigation_and_submission_blocked': browser.get('native_link_navigation_blocked') and browser.get('native_form_submission_blocked'),
        'page_error_count': browser.get('scripted_page_error_count'), 'external_effects': False,
        'release_authorized': False, 'conformance_claim': 'NONE', 'artifact_count': len(artifacts),
        'all_artifact_hashes_verified': True, 'artifacts': artifacts,
        'limitation': 'This exercises one bounded synthetic interaction sample. It does not verify link destination correctness, server response, screen-reader behavior, or WCAG conformance.'}
    EVIDENCE.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({k: evidence[k] for k in ('route','link_interaction_count','form_submission_attempt_count',
        'navigation_and_submission_blocked','artifact_count','all_artifact_hashes_verified','release_authorized')}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build a source-bound grade picker for HOMS Curriculum review cases."""
from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / 'acceptance_runs/68-product-sellability-20261027/HOMS_CURRICULUM_RANDOMIZED_SPINE_CUSTOMER_GRADE_BATCH_20261104_V27'
INPUT_BATCH = ROOT / 'acceptance_runs/68-product-sellability-20261027/HOMS_CURRICULUM_RANDOMIZED_SPINE_SYNTHETIC_GRADE_BATCH_20261104_V27'
ASSIGNMENTS = ROOT / 'deliverables/homs_random_grade_exam_set_20261101/RANDOM_SUBJECT_ASSIGNMENTS.json'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def main() -> None:
    receipt_path = BATCH / 'HOMS_CURRICULUM_RANDOMIZED_SPINE_GRADE_BATCH_RECEIPT.json'
    execution_path = BATCH / 'CUSTOMER_EXECUTION_RECEIPT.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    execution = json.loads(execution_path.read_text(encoding='utf-8'))
    assignment = json.loads(ASSIGNMENTS.read_text(encoding='utf-8'))
    assignment_by_grade = {int(row['grade']): row for row in assignment.get('assignments') or []}
    alignment_path = ROOT / receipt['source_alignment_path']
    rows = sorted(receipt.get('grades') or [], key=lambda row: int(row['grade']))
    if (receipt.get('schema') != 'dio.homs.curriculum.randomized_exam_spine_grade_batch.v1'
            or len(rows) != 12 or [int(row['grade']) for row in rows] != list(range(1, 13))
            or receipt.get('randomized_seed') != 20261101
            or receipt.get('release_authorized') is not False
            or receipt.get('human_curriculum_owner_review_required') is not True
            or receipt.get('term_fit_inferred') is not False
            or receipt.get('candidate_omissions_computed') is not False
            or receipt.get('professional_conclusion') is not False
            or execution.get('batch_receipt_sha256') != sha(receipt_path)
            or execution.get('release_authorized') is not False
            or not alignment_path.is_file()
            or sha(alignment_path) != receipt.get('source_alignment_sha256')
            or assignment.get('random_seed') != 20261101):
        raise ValueError('HOMS Curriculum randomized spine source receipt or held boundary failed')

    cards, output_manifest = [], []
    profile_map = {
        'life_skills': 'Life Skills', 'english_language': 'English Language',
        'mathematics': 'Mathematics', 'natural_sciences_and_technology': 'Natural Sciences and Technology',
        'economics_management_sciences': 'Economic and Management Sciences',
        'life_orientation': 'Life Orientation', 'physical_sciences': 'Physical Sciences',
        'business_studies': 'Business Studies',
    }
    for row in rows:
        grade = int(row['grade'])
        source_assignment = assignment_by_grade.get(grade, {})
        if (row.get('subject_profile') != source_assignment.get('subject_profile')
                or row.get('subject') != profile_map.get(source_assignment.get('subject_profile'))
                or row.get('randomization_seed') != assignment.get('random_seed')):
            raise ValueError(f'Grade {grade} curriculum route no longer matches the randomized subject draw')
        outputs = row.get('outputs') or []
        by_name = {Path(item['path']).name: item for item in outputs}
        wanted = [
            ('Open curriculum review', 'CURRICULUM_REVIEW.html'),
            ('Download alignment matrix', 'CURRICULUM_ALIGNMENT_MATRIX.csv'),
            ('Download plan-entry template', 'CURRICULUM_PLAN_ENTRY_TEMPLATE.csv'),
            ('Inspect source bindings', 'CURRICULUM_SOURCE_BINDING.json'),
            ('Inspect customer packet receipt', 'CUSTOMER_PACKAGE_RECEIPT.json'),
        ]
        links = []
        for label, filename in wanted:
            declared = by_name.get(filename)
            if not declared:
                raise ValueError(f'Grade {grade} curriculum review is missing {filename}')
            path = ROOT / declared['path']
            if not path.is_file() or sha(path) != declared.get('sha256'):
                raise ValueError(f'Grade {grade} curriculum artifact changed: {filename}')
            rel = path.relative_to(BATCH).as_posix()
            if '..' in Path(rel).parts:
                raise ValueError(f'Grade {grade} curriculum artifact escapes its review batch: {filename}')
            output_manifest.append({'grade': grade, 'path': rel, 'sha256': declared['sha256'], 'bytes': path.stat().st_size})
            links.append(f'<a class="link" href="{esc(rel)}">{esc(label)}</a>')
        cards.append(f'''<article class="grade"><div class="number">{grade:02d}</div><div><p class="phase">{esc(row.get('subject_profile','').replace('_',' '))}</p>
<h2>Grade {grade} · {esc(row['subject'])}</h2><p>Five source-topic candidates and one deliberate mismatch are held for curriculum-owner review. The plan-entry template has one blank term/topic row per exam question.</p>
<div class="links">{''.join(links)}</div></div><div class="state"><strong>Review only</strong><span>Seed {row['randomization_seed']}</span><span>CAPS source hash checked</span></div></article>''')

    index_path = BATCH / 'index.html'
    generated = datetime.now(timezone.utc).isoformat()
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HOMS Curriculum · Grades 1–12</title><style>
:root{{--ink:#18292c;--muted:#5c6c6f;--paper:#f3f6f4;--line:#d9e2df;--green:#194b46;--gold:#bd8740}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,sans-serif}}header{{background:#102d32;color:#fff;padding:2.4rem max(1rem,calc((100vw - 1120px)/2))}}
header h1{{font-size:clamp(2rem,4vw,3.1rem);margin:.2rem 0}}header p{{color:#d3e1dd;max-width:780px}}main{{max-width:1120px;margin:auto;padding:1rem}}
.notice{{background:#fff6e5;border-left:5px solid var(--gold);padding:1rem;margin:1rem 0}}.toolbar{{display:flex;gap:.8rem;align-items:center;flex-wrap:wrap;position:sticky;top:0;background:var(--paper);padding:.7rem 0;z-index:2}}
input,button{{font:inherit;padding:.55rem .7rem;border:1px solid #9aada7;border-radius:8px;background:white;color:var(--ink)}}button{{cursor:pointer}}.list{{display:grid;gap:.8rem}}
.grade{{display:grid;grid-template-columns:54px 1fr 180px;gap:1rem;background:white;border:1px solid var(--line);border-radius:13px;padding:1rem;align-items:start}}
.number{{font-size:1.7rem;font-weight:800;color:var(--green)}}h2{{font-size:1.1rem;margin:.15rem 0}}.phase,.state{{font-size:.83rem;color:var(--muted);text-transform:capitalize}}.links{{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.65rem}}
.link{{border:1px solid #cbd8d3;border-radius:7px;padding:.4rem .55rem;background:#f0f5f2;color:#155c56;text-decoration:none;font-size:.87rem}}.state{{display:grid;gap:.3rem;text-align:right}}.state strong{{color:#855200}}footer{{margin:1.5rem 0;color:var(--muted);font-size:.9rem}}.hidden{{display:none!important}}
@media(max-width:700px){{.grade{{grid-template-columns:42px 1fr}}.state{{grid-column:2;text-align:left}}}}@media print{{.toolbar{{display:none}}.grade{{break-inside:avoid}}}}
</style></head><body><header><p>HOMS · CURRICULUM REVIEW</p><h1>Grade mapping review, 1–12</h1>
<p>Open the randomized grade/subject case to compare a supplied plan row with a hash-checked exam-topic source. Each case keeps the candidate and deliberate mismatch visible for curriculum-owner review.</p></header>
<main><section class="notice"><strong>Synthetic review cases; no alignment decision is issued.</strong> The sample plan rows are synthetic. They do not establish complete CAPS coverage, term fit, school-plan truth, omissions, curriculum adequacy, school compliance or approval. Review the complete approved school plan before consequential use.</section>
<section class="toolbar"><label>Filter grade or subject <input id="filter" type="search" placeholder="e.g. Grade 8 or English"></label><span id="count" role="status">12 grades</span></section>
<section class="list">{''.join(cards)}</section><footer>Randomization seed {assignment['random_seed']} · CAPS source alignment: <a href="../../../deliverables/homs_random_grade_exam_set_20261101/CAPS_QUESTION_ALIGNMENT_ALL_GRADES_20261101.json">question alignment map</a><br>Term fit and omission analysis are not computed. Human curriculum-owner review is required; release remains refused.</footer></main>
<script>const rows=[...document.querySelectorAll('.grade')];document.getElementById('filter').addEventListener('input',e=>{{const q=e.target.value.toLowerCase();let n=0;for(const row of rows){{const hide=!row.textContent.toLowerCase().includes(q);row.classList.toggle('hidden',hide);if(!hide)n++}}document.getElementById('count').textContent=n+' grades'}});</script></body></html>'''
    index_path.write_text(page, encoding='utf-8')
    manifest = {
        'schema': 'dio.homs.curriculum.master_index.v1',
        'generated_at_utc': generated,
        'grade_count': 12,
        'grade_range': [1, 12],
        'randomization_seed': assignment['random_seed'],
        'random_subject_assignment_sha256': sha(ASSIGNMENTS),
        'batch_receipt_sha256': sha(receipt_path),
        'batch_execution_receipt_sha256': sha(execution_path),
        'caps_alignment_sha256': sha(alignment_path),
        'human_curriculum_owner_review_required': True,
        'term_fit_inferred': False,
        'candidate_omissions_computed': False,
        'professional_conclusion': False,
        'release_authorized': False,
        'index': {'path': index_path.name, 'sha256': sha(index_path), 'bytes': index_path.stat().st_size},
        'linked_review_artifacts': output_manifest,
    }
    (BATCH / 'HOMS_CURRICULUM_MASTER_INDEX_MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'index': str(index_path.relative_to(ROOT)), 'grade_count': 12,
                      'linked_review_artifact_count': len(output_manifest), 'seed': assignment['random_seed'],
                      'index_sha256': manifest['index']['sha256']}, indent=2))


if __name__ == '__main__':
    main()

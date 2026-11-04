#!/usr/bin/env python3
"""Build a grade picker for the hash-verified HOMS Learning Studio cohort."""
from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / 'deliverables/homs_learning_studio_grade_batch_20261104_V31'
EXAM_SET = ROOT / 'deliverables/homs_random_grade_exam_set_20261101'
AUDIT = ROOT / 'acceptance_runs/68-product-sellability-20261027/HOMS_LEARNING_STUDIO_GRADE_BATCH_AUDIT_20261104_V31.json'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def main() -> None:
    batch_path = BATCH / 'HOMS_LEARNING_STUDIO_GRADE_BATCH_RECEIPT.json'
    assignment_path = EXAM_SET / 'RANDOM_SUBJECT_ASSIGNMENTS.json'
    batch = json.loads(batch_path.read_text(encoding='utf-8'))
    audit = json.loads(AUDIT.read_text(encoding='utf-8'))
    assignments = json.loads(assignment_path.read_text(encoding='utf-8'))
    assignment_rows = {int(row['grade']): row for row in assignments.get('assignments') or []}
    if (batch.get('grade_count') != 12 or batch.get('all_grades_built') is not True
            or batch.get('classroom_release_authorized') is not False
            or batch.get('educator_review_required') is not True
            or audit.get('grade_count') != 12 or audit.get('passed_grade_count') != 12
            or audit.get('all_grade_sources_and_outputs_verified') is not True
            or audit.get('source_batch_receipt_sha256') != digest(batch_path)
            or audit.get('random_subject_assignments_sha256') != digest(assignment_path)
            or assignments.get('random_seed') != 20261101):
        raise ValueError('HOMS Learning Studio source batch, randomization, or audit is incomplete')

    cards, artifact_rows = [], []
    grade_rows = sorted(batch.get('grades') or [], key=lambda row: int(row['grade']))
    if [int(row['grade']) for row in grade_rows] != list(range(1, 13)):
        raise ValueError('HOMS Learning Studio batch must contain each grade exactly once')
    for row in grade_rows:
        grade = int(row['grade'])
        subject_profile = str(assignment_rows.get(grade, {}).get('subject_profile') or '')
        expected_subject = {
            'life_skills': 'Life Skills',
            'english_language': 'English Language',
            'mathematics': 'Mathematics',
            'natural_sciences_and_technology': 'Natural Sciences and Technology',
            'economics_management_sciences': 'Economic and Management Sciences',
            'life_orientation': 'Life Orientation',
            'physical_sciences': 'Physical Sciences',
            'business_studies': 'Business Studies',
        }.get(subject_profile)
        if expected_subject is None:
            raise ValueError(f'Grade {grade} has an unknown randomized subject profile: {subject_profile}')
        # The audit keeps the catalog display name and is the independent binding between sources.
        audited = next((item for item in audit.get('grades') or [] if int(item.get('grade') or 0) == grade), {})
        subject = str(row['subject'])
        if subject.casefold() != expected_subject.casefold() or audited.get('subject') != subject:
            raise ValueError(f'Grade {grade} subject no longer matches the seeded assignment and source audit')
        files = {Path(item['path']).name: item for item in row.get('files') or []}
        links = [
            ('Open complete grade pack', f'grade-{grade:02d}/index.html', 'index.html'),
            ('Interactive educator lesson planner', f'grade-{grade:02d}/EDUCATOR_LESSON_PLANNER.html', 'EDUCATOR_LESSON_PLANNER.html'),
            ('Learner revision guide (PDF)', f'grade-{grade:02d}/pdf/HOMS_LEARNER_REVISION_ROUTE.pdf', 'HOMS_LEARNER_REVISION_ROUTE.pdf'),
            ('Educator lesson and marking map (PDF)', f'grade-{grade:02d}/pdf/HOMS_EDUCATOR_LESSON_AND_MARKING_MAP.pdf', 'HOMS_EDUCATOR_LESSON_AND_MARKING_MAP.pdf'),
            ('Exam paper (PDF)', f'grade-{grade:02d}/pdf/HOMS_EXAM_STUDIO_FIRST_OPPORTUNITY_PAPER.pdf', 'HOMS_EXAM_STUDIO_FIRST_OPPORTUNITY_PAPER.pdf'),
            ('Marking memo (PDF)', f'grade-{grade:02d}/pdf/HOMS_EXAM_STUDIO_FIRST_OPPORTUNITY_MEMO.pdf', 'HOMS_EXAM_STUDIO_FIRST_OPPORTUNITY_MEMO.pdf'),
            ('Assessment-linked bundle (ZIP)', f'grade-{grade:02d}/HOMS_LEARNING_STUDIO_ASSESSMENT_LINKED_BUNDLE.zip', 'HOMS_LEARNING_STUDIO_ASSESSMENT_LINKED_BUNDLE.zip'),
        ]
        rendered_links = []
        for label, rel, filename in links:
            path = BATCH / rel
            if not path.is_file():
                raise ValueError(f'Grade {grade} Learning Studio output is missing: {rel}')
            source_entry = files.get(filename)
            expected_hash = source_entry.get('sha256') if source_entry else None
            if not expected_hash or digest(path) != expected_hash:
                raise ValueError(f'Grade {grade} Learning Studio output is not bound by its batch receipt: {rel}')
            artifact_rows.append({'grade': grade, 'path': rel, 'sha256': digest(path), 'bytes': path.stat().st_size})
            rendered_links.append(f'<a class="link" href="{esc(rel)}">{esc(label)}</a>')
        cards.append(f'''<article class="grade-card"><div class="grade-number">{grade:02d}</div>
<div class="grade-main"><p class="phase">{esc(row.get('phase','').replace('_',' '))}</p>
<h2>Grade {grade} · {esc(subject)}</h2><p>{row.get('question_count',0)} source-bound exam prompts · educator review required</p>
<div class="links">{''.join(rendered_links)}</div></div>
<div class="status"><strong>Draft · held</strong><span>Seed {assignments['random_seed']}</span><span>Video: {esc(row.get('video_bundle_status','not verified'))}</span></div></article>''')

    index = BATCH / 'index.html'
    stamp = datetime.now(timezone.utc).isoformat()
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HOMS Learning Studio · Grades 1–12</title><style>
:root{{--ink:#17282b;--muted:#596b6e;--paper:#f2f5f3;--card:#fff;--line:#d9e2df;--green:#194b46;--gold:#bd8740}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,sans-serif}}header{{background:#102d32;color:#fff;padding:2.5rem max(1rem,calc((100vw - 1120px)/2))}}
header h1{{font-size:clamp(2rem,4vw,3.2rem);line-height:1.1;margin:.2rem 0}}header p{{max-width:780px;color:#d4e3df}}main{{max-width:1120px;margin:auto;padding:1.2rem}}
.notice{{background:#fff7e8;border-left:5px solid var(--gold);padding:1rem;margin:1rem 0}}.toolbar{{position:sticky;top:0;z-index:2;background:var(--paper);padding:.75rem 0;display:flex;gap:.7rem;flex-wrap:wrap}}
input,select,button{{font:inherit;padding:.55rem .7rem;border:1px solid #9eb0aa;border-radius:8px;background:#fff;color:var(--ink)}}button{{cursor:pointer}}
.grade-list{{display:grid;gap:.9rem}}.grade-card{{display:grid;grid-template-columns:64px 1fr 190px;gap:1rem;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:1rem;align-items:start}}
.grade-number{{font-size:1.8rem;font-weight:800;color:var(--green)}}h2{{font-size:1.15rem;margin:.1rem 0}}.phase,.status{{font-size:.82rem;color:var(--muted);text-transform:capitalize}}.links{{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.7rem}}.link{{background:#eff5f2;border:1px solid #cbd9d3;border-radius:7px;padding:.4rem .6rem;color:#155e57;text-decoration:none;font-size:.88rem}}.link:hover{{background:#dfece6}}.status{{display:grid;gap:.35rem;text-align:right}}.status strong{{color:#8a5600}}footer{{margin:1.5rem 0;color:var(--muted);font-size:.9rem}}.hidden{{display:none!important}}
@media(max-width:760px){{.grade-card{{grid-template-columns:48px 1fr}}.status{{grid-column:2;text-align:left}}}}@media print{{.toolbar{{display:none}}body{{background:white}}.grade-card{{break-inside:avoid}}}}
</style></head><body><header><p>HOMS · LEARNING STUDIO</p><h1>Grade packs, 1–12</h1>
<p>Choose the randomized grade and subject to open its learner guide, educator lesson and marking map, paired exam and memo, and editable lesson planner.</p></header>
<main><section class="notice"><strong>Educator review is required.</strong> The packs are source-bound drafts, not a claim of complete CAPS coverage or classroom approval. No video matched the exact grade scope in this batch; storyboard files are drafts. Classroom release remains blocked pending educator approval.</section>
<div class="toolbar"><label>Filter by grade or subject <input id="filter" type="search" placeholder="e.g. Grade 10 or Mathematics"></label><button id="print">Print grade list</button><span id="count" role="status">12 grade packs</span></div>
<section class="grade-list" id="grades">{''.join(cards)}</section>
<footer>Seeded assignment: {assignments['random_seed']} · {esc(assignments.get('selection_method',''))}<br>Batch receipt and grade outputs were hash-audited; the paired exam/memo remains subject to educator review.</footer></main>
<script>const cards=[...document.querySelectorAll('.grade-card')];document.getElementById('filter').addEventListener('input',e=>{{const q=e.target.value.toLowerCase();let n=0;for(const c of cards){{const hide=!c.textContent.toLowerCase().includes(q);c.classList.toggle('hidden',hide);if(!hide)n++}}document.getElementById('count').textContent=n+' grade packs'}});document.getElementById('print').addEventListener('click',()=>window.print());</script></body></html>'''
    index.write_text(page, encoding='utf-8')
    manifest = {
        'schema': 'dio.homs.learning_studio.master_index.v1',
        'generated_at_utc': stamp,
        'grade_count': len(grade_rows),
        'grade_range': [1, 12],
        'random_seed': assignments['random_seed'],
        'assignment_manifest_sha256': digest(assignment_path),
        'batch_receipt_sha256': digest(batch_path),
        'batch_audit_sha256': digest(AUDIT),
        'classroom_release_authorized': False,
        'educator_approval_required': True,
        'index': {'path': index.name, 'sha256': digest(index), 'bytes': index.stat().st_size},
        'linked_grade_outputs': artifact_rows,
    }
    (BATCH / 'HOMS_LEARNING_STUDIO_MASTER_INDEX_MANIFEST.json').write_text(
        json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'index': str(index.relative_to(ROOT)), 'grade_count': len(grade_rows),
                      'linked_output_count': len(artifact_rows), 'random_seed': assignments['random_seed'],
                      'index_sha256': manifest['index']['sha256']}, indent=2))


if __name__ == '__main__':
    main()

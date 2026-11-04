#!/usr/bin/env python3
"""Audit that HOMS Assess withholds scores when source/feedback flags remain."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'acceptance_runs/68-product-sellability-20261027'
INPUT = BASE / 'homs-assess-corrected-grade10-quality-review-20261101/homs-assess/PROJECTION/homs_hymark_input'
JOB = BASE / 'HOMS_ASSESS_SCORE_WITHHOLD_FLAGS_20261102_V2/homs-hymark-homs_hymark_input-20261101T132418Z'
REPEAT_JOB = BASE / 'HOMS_ASSESS_SCORE_WITHHOLD_FLAGS_20261102_V3/homs-hymark-homs_hymark_input-20261101T132730Z'
OUTPUT = BASE / 'HOMS_ASSESS_SCORE_WITHHOLDING_EVIDENCE_20261102.json'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    receipt = json.loads((JOB / 'HOMS_HYMARK_BATCH_RECEIPT.json').read_text(encoding='utf-8'))
    results = json.loads((JOB / 'results.json').read_text(encoding='utf-8'))
    repeat_receipt = json.loads((REPEAT_JOB / 'HOMS_HYMARK_BATCH_RECEIPT.json').read_text(encoding='utf-8'))
    repeat_results = json.loads((REPEAT_JOB / 'results.json').read_text(encoding='utf-8'))
    marks = {row['student_id']: row for row in csv.DictReader((JOB / 'marks.csv').open(encoding='utf-8', newline=''))}
    repeat_marks = {row['student_id']: row for row in csv.DictReader((REPEAT_JOB / 'marks.csv').open(encoding='utf-8', newline=''))}
    summary = (JOB / 'LECTURER_REVIEW_SUMMARY.md').read_text(encoding='utf-8')
    flagged = [row for row in results if row.get('marking_quality_flags')]
    unflagged = [row for row in results if not row.get('marking_quality_flags')]
    def signature(rows):
        return [(row.get('student_id'), row.get('total_score'), row.get('proposed_total_score'), row.get('score_status'), sorted(flag.get('code') for flag in row.get('marking_quality_flags', []))) for row in rows]
    input_hashes = {str(path.relative_to(INPUT)): sha256(path) for path in sorted(INPUT.rglob('*')) if path.is_file()}
    checks = {
        'original_question_paper_present': any(path.is_file() for path in INPUT.glob('uploads/*question_paper*')),
        'local_model_and_temperature_recorded': receipt.get('provider', {}).get('selected_provider') == 'ollama' and receipt.get('provider', {}).get('temperature') == 0.0,
        'repeat_uses_same_model_temperature_and_input': (repeat_receipt.get('provider', {}).get('selected_provider') == receipt.get('provider', {}).get('selected_provider') and repeat_receipt.get('provider', {}).get('selected_model') == receipt.get('provider', {}).get('selected_model') and repeat_receipt.get('provider', {}).get('temperature') == receipt.get('provider', {}).get('temperature') and repeat_receipt.get('input_dir') == receipt.get('input_dir') and repeat_receipt.get('input_dir') == str(INPUT.resolve())),
        'configured_repeat_scores_and_flags_match': signature(results) == signature(repeat_results),
        'repeat_also_withholds_flagged_score': bool(flagged) and all(repeat_marks[row['student_id']].get('score') == '' and repeat_marks[row['student_id']].get('proposed_score') != '' for row in flagged),
        'provider_completed_without_errors': receipt.get('status') == 'completed' and not receipt.get('provider_errors'),
        'at_least_one_quality_flagged_learner': bool(flagged),
        'flagged_scores_withheld_from_result_fields': bool(flagged) and all(row.get('score_status', '').startswith('BLOCKED_') and row.get('total_score') is None and row.get('percentage') is None and isinstance(row.get('proposed_total_score'), (int, float)) for row in flagged),
        'flagged_scores_blank_in_marks_csv': bool(flagged) and all(marks[row['student_id']].get('score') == '' and marks[row['student_id']].get('proposed_score') != '' for row in flagged),
        'flagged_scores_reported_not_scored': bool(flagged) and all(f"- {row['student_id']}: NOT SCORED" in summary for row in flagged),
        'unflagged_scores_remain_provisional': bool(unflagged) and all(row.get('score_status') == 'PROVISIONAL_EDUCATOR_REVIEW_REQUIRED' and isinstance(row.get('total_score'), (int, float)) for row in unflagged),
        'receipt_declares_flagged_score_block': receipt.get('score_issuance') == 'BLOCKED_MARKING_QUALITY_FLAGS',
        'review_pack_present': Path(receipt['outputs']['review_zip']).is_file(),
    }
    if not all(checks.values()):
        raise SystemExit('HOMS Assess score withholding audit failed: ' + json.dumps(checks, sort_keys=True))
    artifact_paths = [
        INPUT / 'rubric.json', INPUT / 'memo.md', INPUT / 'uploads/question_paper.md',
        INPUT / 'uploads/learner_A.txt', INPUT / 'uploads/learner_B.txt',
        JOB / 'HOMS_HYMARK_BATCH_RECEIPT.json', JOB / 'results.json', JOB / 'marks.csv',
        JOB / 'LECTURER_REVIEW_SUMMARY.md', Path(receipt['outputs']['review_zip']),
        REPEAT_JOB / 'HOMS_HYMARK_BATCH_RECEIPT.json', REPEAT_JOB / 'results.json',
        REPEAT_JOB / 'marks.csv', REPEAT_JOB / 'LECTURER_REVIEW_SUMMARY.md',
        Path(repeat_receipt['outputs']['review_zip']),
    ]
    artifacts = [{'path': str(path.relative_to(ROOT)), 'sha256': sha256(path), 'bytes': path.stat().st_size} for path in artifact_paths]
    report = {
        'schema': 'dio.homs.assess.score_withholding_evidence.v1',
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'product': 'HOMS Assess',
        'execution': {'provider': receipt['provider']['selected_provider'], 'model': receipt['provider']['selected_model'], 'temperature': receipt['provider']['temperature'], 'score_issuance': receipt['score_issuance'], 'learner_count': len(results), 'flagged_score_count': len(flagged), 'unflagged_provisional_count': len(unflagged)},
        'repeatability': {'classification': 'TWO_IDENTICAL_CONFIGURED_RUNS_MATCHED' if checks['configured_repeat_scores_and_flags_match'] else 'CONFIGURED_REPEAT_VARIANCE_FOUND', 'repeat_job_receipt': str((REPEAT_JOB / 'HOMS_HYMARK_BATCH_RECEIPT.json').relative_to(ROOT)), 'input_file_sha256': input_hashes, 'boundary': 'Two controlled repeat runs only; this observation is not a general guarantee of future determinism.'},
        'checks': checks,
        'all_checks_pass': True,
        'learner_rows': [{'score_status': row['score_status'], 'score_issued': row.get('total_score') is not None, 'quality_flag_codes': sorted({flag['code'] for flag in row.get('marking_quality_flags', [])})} for row in results],
        'artifacts': artifacts,
        'claim_boundary': 'Controlled synthetic Grade 10 submissions. A flagged score is withheld from issued score fields and the CSV score column; an unflagged score remains provisional. This does not establish marking correctness, educator acceptance, or classroom release.',
    }
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(OUTPUT.relative_to(ROOT)), 'all_checks_pass': True, 'flagged_scores': len(flagged), 'unflagged_provisional_scores': len(unflagged), 'artifact_count': len(artifacts)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Refresh grade-batch evidence after source-owned item and memo corrections."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from docx import Document

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'deliverables/homs_random_grade_exam_set_20261101'
ASSIGNMENTS = json.loads((PACK / 'RANDOM_SUBJECT_ASSIGNMENTS.json').read_text(encoding='utf-8'))
SET = json.loads((PACK / 'GRADE_EXAM_SET_RECEIPT.json').read_text(encoding='utf-8'))
CORRECTION = {
    'grade': 2, 'question_id': '1.4',
    'previous_prompt': "1.4 Rewrite the sentence to describe one shoot: 'Two small green shoots had appeared.' [4]",
    'updated_prompt': "1.4 Change this sentence to describe one pot: 'The pots are near a sunny window.' [4]",
    'reason': 'The prior item used a past-perfect construction beyond the Grade 2 English FAL language structures listed in the cited CAPS. The replacement assesses plural forms and singular agreement with the verb to be in a simple present-tense sentence, retaining one mark each for noun, verb, determiner and sentence punctuation.',
}
GRADE3_CORRECTION = {
    'grade': 3, 'question_id': '1.2',
    'previous_prompt': '1.2 Put all the tops into bags of 6. How many full bags can be made? [4]',
    'updated_prompt': '1.2 Use your total from Question 1.1 to put the bottle tops into bags of 6. Show a calculation or equal-groups drawing. State how many full bags you can make and whether any tops are left. [4]',
    'reason': "The original four-mark question did not request a method or remainder, and the first memo version did not award full carry-forward credit when the earlier addition was wrong. The revised prompt requests method and remainder; the memo now independently awards a consistently correct quotient/remainder and result for the learner's carried-forward total.",
}
GRADE4_CORRECTION = {
    'grade': 4, 'question_id': '1.4',
    'previous_prompt': '1.4 The class has 360 seeds and plants 145. How many seeds remain? [7]',
    'updated_prompt': '1.4 The class has 360 seeds and plants 145. Show the column subtraction, make any regrouping clear, and check your answer with addition. How many seeds remain? [7]',
    'reason': 'The original seven-mark question asked only for a subtraction result. The revised wording requires visible column method, regrouping and an inverse addition check so the seven allocated marks assess requested work.',
}
GRADE4_CAPACITY_CORRECTION = {
    'grade': 4, 'question_id': '1.5',
    'previous_prompt': '1.5 Each seedling needs 250 mL of water. How many millilitres are needed for 8 seedlings? Express the total in litres too. [7]',
    'updated_prompt': '1.5 Each seedling needs 250 mL of water. For 8 seedlings, show the multiplication and the conversion calculation. Give the total in millilitres and litres. [6]',
    'reason': 'The previous seven-mark prompt did not request the working that its rubric assessed and awarded separate marks for overlapping conversion/result/unit criteria. The revision explicitly requests multiplication and conversion work, reduces the item to six distinct marking points, and binds the conversion claim to Grade 4 CAPS physical page 93.',
}
GRADE4_FRACTION_CORRECTION = {
    'grade': 4, 'question_id': '1.3',
    'previous_prompt': '1.3 The learners plant 48 seedlings. What fraction of 192 is 48? Simplify it. [6]',
    'updated_prompt': '1.3 What fraction of the 192 seedlings is 48? Simplify it. Show how you simplify the fraction and check your answer. [6]',
    'reason': 'The earlier memo awarded separate marks for showing an equivalent fraction and stating the same simplified answer, which could reward the same result twice. The revised prompt requests a visible simplification method and check; the six memo points distinguish the starting fraction, common divisor, numerator and denominator operations, simplified result, and inverse check.',
}
GRADE5_CORRECTION = {
    'grade': 5, 'question_id': '1.1–1.5',
    'previous_prompt': 'A five-question Grade 5 science assessment about sand/water mixtures and ice melting, mapped largely to unrelated metals and processing-material pages.',
    'updated_prompt': 'A five-question Grade 5 assessment on processing materials, the CAPS concrete example, before/after properties, fair testing, evidence recording and limits of small-sample conclusions.',
    'reason': 'The previous scenario and question mappings did not align: mixture separation and ice melting were cited to metals/non-metals and unrelated flour-paste content. All five items now use the Grade 5 Term 2 concrete-processing example and Grades 4–6 investigation skills, with source pages matched to the assessed concept. Item-level memo revisions now award three distinct controls separately, specify before/after property evidence, and request two distinct reliability actions where those actions receive separate marks.',
}
GRADE7_CORRECTION = {
    'grade': 7, 'question_id': '1.1',
    'previous_prompt': '1.1 For each item, say whether it is used to make the fruit cups, is a business expense, or both. Explain your choices for the fruit and the table fee. [6]',
    'updated_prompt': '1.1 Classify these four items—fruit bought, cups bought, table fee, and money received from cups sold—as a production input, business expense, sales revenue, or all categories that apply. Explain why the fruit and table fee fit their categories. [6]',
    'reason': 'The earlier revision still said “for each item” without naming the items and did not include sales revenue as a response category, although the memo expected learners to distinguish revenue. The corrected prompt names all four items, makes overlapping categories explicit, and aligns six separate one-mark memo points to each classification and the two requested explanations.',
    'previous_memo_points': [
        'Identifies fruit as a material used to make the fruit cups. The R90 purchase is also a business expense. (Accept both roles.)',
        'Identifies the table fee as a business expense.',
        'Explains that fruit is used in the product being made.',
        'Explains that the table fee pays for selling space at the market.',
        'Distinguishes a production input from sales revenue.',
        'Recognises that one item can be both a production input and an expense; the categories are not mutually exclusive.',
    ],
    'updated_memo_points': [
        'Classifies the fruit bought as both a production input and a business expense.',
        'Classifies the cups bought as both a production input and a business expense.',
        'Classifies the table fee as a business expense.',
        'Classifies money received from cups sold as sales revenue, not a business expense.',
        'Explains that the fruit is used in the product and its purchase is an outlay.',
        'Explains that the table fee pays for market selling space.',
    ],
}
GRADE10_CORRECTION = {
    'grade': 10, 'question_id': '1.4',
    'previous_prompt': '1.4 If the later acceleration stays constant for 3 more seconds, calculate the new velocity. [11]',
    'updated_prompt': '1.4 Assume the later acceleration stays constant at the value from Question 1.3 for a further 3 s, starting at +15 m·s⁻¹. Calculate the final velocity and signed displacement. Draw a velocity-time graph for this interval or show the trapezium area calculation, and state the direction. [11]',
    'reason': 'The original eleven-mark item asked only for one velocity calculation and referred to a graph that was not supplied. The revised prompt provides all values through the stimulus and Question 1.3, and asks learners to draw the graph or show the trapezium-area method for displacement.',
}
GRADE10_REASONING_CORRECTION = {
    'grade': 10, 'question_id': '1.1–1.2',
    'previous_prompt': 'Distance and displacement were calculated for a straight journey without a reversal; average velocity was calculated without average speed.',
    'updated_prompt': "During the first 6 s, the trolley travels east from -4 m to +20 m in 4 s, then reverses to +8 m by t = 6 s. Learners calculate distance and displacement, then average velocity and average speed.",
    'reason': 'The specified reversal makes total path length distinct from change in position. The paired six-second average-speed and average-velocity calculations use the same unambiguous distance, displacement and time data, and the memo awards separate method, result, direction and unit points.',
}
CORRECTIONS = [CORRECTION, GRADE3_CORRECTION, GRADE4_CORRECTION, GRADE4_FRACTION_CORRECTION, GRADE5_CORRECTION, GRADE7_CORRECTION, GRADE10_CORRECTION, GRADE10_REASONING_CORRECTION]
MODERATION = ROOT / 'acceptance_runs/68-product-sellability-20261027/HOMS_MODERATE_CUSTOMER_GRADE_BATCH_20261104_V35/HOMS_MODERATE_CUSTOMER_GRADE_BATCH_RECEIPT.json'

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def docx_text(path: Path) -> str:
    doc = Document(path)
    values = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        values.extend(' | '.join(cell.text for cell in row.cells) for row in table.rows)
    return '\n'.join(values)

def main() -> int:
    moderation = json.loads(MODERATION.read_text(encoding='utf-8'))
    moderation_by_grade = {int(row['grade']): row for row in moderation.get('results', [])}
    if moderation.get('grade_count') != 12 or moderation.get('mechanical_pass_count') != 12:
        raise ValueError('Current HOMS Moderate batch is not a complete 12-grade pass')
    results = []
    assignments = {int(row['grade']): row for row in ASSIGNMENTS['assignments']}
    checks = []
    for entry in SET['results']:
        grade = int(entry['grade'])
        folder = Path(entry['job_dir'])
        if not folder.is_absolute(): folder = ROOT / folder
        assessment_path = folder / 'HOMS_GRADE_ASSESSMENT.json'
        receipt_path = folder / 'HOMS_GRADE_EXAM_RECEIPT.json'
        assessment = json.loads(assessment_path.read_text(encoding='utf-8'))
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        questions = [q for section in assessment['sections'] for q in section['questions']]
        total = sum(int(q['marks']) for q in questions)
        memo_total = sum(int(point['marks']) for q in questions for point in q['memo'])
        exam, memo = folder / 'GRADE_EXAM.docx', folder / 'GRADE_MEMO.docx'
        assignment = assignments[grade]
        row = {'grade': grade, 'subject': assessment['subject'], 'subject_profile': assignment['subject_profile'],
               'caps_phase': assignment['phase'], 'total_marks': total, 'question_count': len(questions),
               'memo_mark_points': memo_total, 'caps_source_sha256': receipt['caps_source']['sha256'],
               'exam': {'path': exam.relative_to(PACK).as_posix(), 'bytes': exam.stat().st_size, 'sha256': digest(exam)},
               'memo': {'path': memo.relative_to(PACK).as_posix(), 'bytes': memo.stat().st_size, 'sha256': digest(memo)},
               'assessment_json_sha256': digest(assessment_path),
               'question_marks_match': len(questions) == 5 and all(sum(int(x['marks']) for x in q['memo']) == int(q['marks']) for q in questions),
               'memo_points_reconcile': total == memo_total,
               'mechanical_moderation': 'PASS',
               'release_authorized': False, 'educator_review_required': True}
        for role, path in (('exam', exam), ('memo', memo), ('json', assessment_path)):
            if receipt['assessment'][role]['sha256'] != digest(path):
                raise ValueError(f'Grade {grade} {role} hash mismatch against its receipt')
        if len(questions) != 5 or total != int(assessment['total_marks']) or memo_total != total:
            raise ValueError(f'Grade {grade} question/memo totals do not reconcile')
        moderation_row = moderation_by_grade.get(grade, {})
        if (moderation_row.get('mechanical_state') != 'PASS'
                or moderation_row.get('source_exam_sha256') != digest(exam)
                or moderation_row.get('source_memo_sha256') != digest(memo)):
            raise ValueError(f'Grade {grade} moderation is not bound to the current exam and memo')
        if not docx_text(exam).strip() or not docx_text(memo).strip():
            raise ValueError(f'Grade {grade} DOCX did not reopen with content')
        if grade == 2:
            q = next(q for q in questions if q.get('number') == '1.4')
            if q['prompt'] != CORRECTION['updated_prompt'] or len(q['memo']) != 4:
                raise ValueError('Grade 2 sentence transformation does not match the source correction')
            if any(point['point'] not in docx_text(memo) for point in q['memo']):
                raise ValueError('Grade 2 revised memo points are not present in the rendered memo')
            exam_normalized = ' '.join(docx_text(exam).split())
            if "Change this sentence to describe one pot: 'The pots are near a sunny window.' [4]" not in exam_normalized:
                raise ValueError('Grade 2 revised prompt is not present in the rendered exam')
        if grade in (3, 4, 7, 10):
            correction = {3: GRADE3_CORRECTION, 4: GRADE4_CORRECTION, 7: GRADE7_CORRECTION, 10: GRADE10_CORRECTION}[grade]
            target_question = next(q for q in questions if q.get('number') == correction['question_id'])
            exam_normalized = ' '.join(docx_text(exam).split())
            if target_question['prompt'] != correction['updated_prompt'] or target_question['marks'] != sum(int(point['marks']) for point in target_question['memo']):
                raise ValueError(f'Grade {grade} revised prompt or memo allocation does not match its correction record')
            if correction['updated_prompt'] not in exam_normalized or any(point['point'] not in docx_text(memo) for point in target_question['memo']):
                raise ValueError(f'Grade {grade} revised exam or memo text is missing from the rendered files')
        if grade == 10:
            exam_normalized = ' '.join(docx_text(exam).split())
            updated_prompts = [
                "1.1 Distinguish distance and displacement, then calculate both for the trolley's first 6 s of motion. [8]",
                '1.2 For the first 6 s, calculate the trolley\'s average velocity and average speed. State one difference between them. [9]',
            ]
            if any(prompt not in exam_normalized for prompt in updated_prompts):
                raise ValueError('Grade 10 reversal and average-speed prompts are missing from the rendered exam')
            for number in ('1.1', '1.2'):
                item = next(q for q in questions if q.get('number') == number)
                if len(item['memo']) != item['marks'] or any(point['point'] not in docx_text(memo) for point in item['memo']):
                    raise ValueError(f'Grade 10 {number} source memo points do not reconcile with the rendered memo')
        if grade == 4:
            fraction_prompt = GRADE4_FRACTION_CORRECTION['updated_prompt']
            fraction_question = next(q for q in questions if q.get('number') == '1.3')
            fraction_exam_text = ' '.join(docx_text(exam).split())
            if (fraction_question['prompt'] != fraction_prompt or len(fraction_question['memo']) != 6
                    or fraction_prompt not in fraction_exam_text
                    or any(point['point'] not in docx_text(memo) for point in fraction_question['memo'])):
                raise ValueError('Grade 4 fraction method/check item or memo points do not match the correction record')
        results.append(row)
        checks.append(all((row['question_marks_match'], row['memo_points_reconcile'], receipt['release_authorized'] is False)))
    if len(results) != 12 or not all(checks): raise ValueError('Expected 12 fully reconciled held draft grade packs')
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    audit = {'schema':'dio.homs.random_grade_exam_memo_artifact_audit.v1','created_at':now,'grade_count':12,
             'grade_range':[1,12],'random_seed':ASSIGNMENTS['random_seed'],
             'subject_randomization_method':ASSIGNMENTS['selection_method'],'grades':results,
             'all_docx_hash_receipts_match':True,'all_question_marks_reconcile':True,
             'all_memo_points_reconcile':True,'all_12_mechanical_moderation_runs_pass':True,
             'latest_moderation_receipt_sha256':digest(MODERATION),
             'educator_review_required':True,'classroom_release_authorized':False,
             'content_correction':GRADE4_CORRECTION,'content_corrections':CORRECTIONS}
    (PACK/'HOMS_RANDOM_GRADE_EXAM_MEMO_ARTIFACT_AUDIT_20261101.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    product_path=PACK/'HOMS_PRODUCT_BATCH_EVIDENCE.json'
    product=json.loads(product_path.read_text(encoding='utf-8'))
    by_grade={row['grade']:row for row in results}
    for row in product.get('grades',[]):
        current=by_grade[int(row['grade'])]
        row['exam']['sha256']=current['exam']['sha256']
        row['memo']['sha256']=current['memo']['sha256']
        row['assessment_json']['sha256']=current['assessment_json_sha256']
    product['last_content_revision']={'grade':10,'question_id':'1.1–1.2','reason':GRADE10_REASONING_CORRECTION['reason'],'exam_sha256':by_grade[10]['exam']['sha256'],'memo_sha256':by_grade[10]['memo']['sha256']}
    for correction in product.get('source_metadata_corrections', []):
        if int(correction.get('grade', 0)) == 7:
            correction['exam_sha256'] = by_grade[7]['exam']['sha256']
            correction['memo_sha256'] = by_grade[7]['memo']['sha256']
    existing_corrections = [item for item in product.get('content_corrections', []) if int(item.get('grade', 0)) not in {2, 3, 4, 7, 10}]
    product['content_corrections'] = existing_corrections + [
        {'grade':2,'question_id':'1.4','issue':'Four marks were assigned to an under-specified phrase-only singular transformation.','resolution':'Reframed as a full sentence rewrite and aligned the four memo points to quantity, noun number, adjective retention, and sentence punctuation.','exam_sha256':by_grade[2]['exam']['sha256'],'memo_sha256':by_grade[2]['memo']['sha256']},
        {'grade':3,'question_id':'1.2','issue':'Four marks were assigned to an equal-grouping item that did not request working or a remainder.','resolution':'Asked for the method and leftover tops; the memo grants carry-forward credit and distinguishes quotient, remainder and reported result.','exam_sha256':by_grade[3]['exam']['sha256'],'memo_sha256':by_grade[3]['memo']['sha256']},
        {'grade':4,'question_id':'1.4','issue':'Seven marks were assigned to a single subtraction result without requiring visible working or verification.','resolution':'Asked for column subtraction, visible regrouping and an inverse addition check; the seven memo points now correspond to these requested steps.','exam_sha256':by_grade[4]['exam']['sha256'],'memo_sha256':by_grade[4]['memo']['sha256']},
        {'grade':4,'question_id':'1.3','issue':'The memo awarded both an equivalent fraction and the same simplified fraction as separate points.','resolution':'Asked learners to show simplification and verify the result; revised points now separate the starting ratio, common divisor, numerator/denominator operations, simplest form and check.','exam_sha256':by_grade[4]['exam']['sha256'],'memo_sha256':by_grade[4]['memo']['sha256']},
        {'grade':5,'question_id':'1.1–1.5','issue':'The five-question scenario assessed sand/water separation and ice melting while its CAPS maps cited unrelated metals and flour/water processing content.','resolution':'Rebuilt the assessment around the Grade 5 CAPS concrete-processing example, before/after properties and explicit fair-test/recording skills; rebound each question to relevant official pages.','exam_sha256':by_grade[5]['exam']['sha256'],'memo_sha256':by_grade[5]['memo']['sha256']},
        {'grade':7,'question_id':'1.1','issue':'The wording treated production input and expense as alternatives, although the fruit is both an input and an expense.','resolution':'Reworded the item to permit both roles and updated its six one-mark memo points to distinguish the input, expense, table fee, sales purpose and overlapping categories.','exam_sha256':by_grade[7]['exam']['sha256'],'memo_sha256':by_grade[7]['memo']['sha256']},
        {'grade':10,'question_id':'1.4','issue':'Eleven marks were assigned to one final-velocity calculation.','resolution':'Expanded the item to require both final velocity and signed displacement from the velocity-time graph area, then mapped it to the relevant official CAPS motion/graph pages.','exam_sha256':by_grade[10]['exam']['sha256'],'memo_sha256':by_grade[10]['memo']['sha256']},
        {'grade':10,'question_id':'1.1–1.2','issue':'A no-reversal path made distance equal displacement, and the follow-up assessed average velocity without average speed.','resolution':'Specified a return segment so distance is 36 m while displacement is +12 m, then asked for both average speed (6 m·s⁻¹) and average velocity (+2 m·s⁻¹ east) over the same six seconds.','exam_sha256':by_grade[10]['exam']['sha256'],'memo_sha256':by_grade[10]['memo']['sha256']},
    ]
    product['mechanical_validation']={'grade_range_complete':True,'question_count_each':5,'exact_marks_all_grades':True,'memo_points_equal_marks':True,'docx_files_present_and_openable':True}
    product_path.write_text(json.dumps(product,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (PACK/'GRADE02_CONTENT_CORRECTION_20261102.json').write_text(json.dumps({'schema':'dio.homs.grade_exam_content_correction.v1','created_at':now,**CORRECTION,'corrected_exam_sha256':by_grade[2]['exam']['sha256'],'corrected_memo_sha256':by_grade[2]['memo']['sha256'],'corrected_assessment_sha256':by_grade[2]['assessment_json_sha256'],'question_mark_total':4,'memo_mark_total':4,'educator_review_required':True,'classroom_release_authorized':False,'claim_boundary':'Source-owned item clarity correction and mechanical artifact reconciliation only; no independent educator approval.'},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    for correction, grade in ((GRADE3_CORRECTION, 3), (GRADE4_CORRECTION, 4), (GRADE5_CORRECTION, 5), (GRADE7_CORRECTION, 7), (GRADE10_CORRECTION, 10)):
        assessment = json.loads((Path(SET['results'][grade-1]['job_dir'])/'HOMS_GRADE_ASSESSMENT.json').read_text(encoding='utf-8'))
        questions = assessment['sections'][0]['questions']
        selected = questions if correction['question_id'] == '1.1–1.5' else [q for q in questions if q['number'] == correction['question_id']]
        if not selected:
            raise ValueError(f"Grade {grade} correction does not bind to source questions")
        evidence = {'schema':'dio.homs.grade_exam_content_correction.v1','created_at':now,**correction,
                    'corrected_exam_sha256':by_grade[grade]['exam']['sha256'],
                    'corrected_memo_sha256':by_grade[grade]['memo']['sha256'],
                    'corrected_assessment_sha256':by_grade[grade]['assessment_json_sha256'],
                    'question_mark_total':sum(int(q['marks']) for q in selected),
                    'memo_mark_total':sum(int(point['marks']) for q in selected for point in q['memo']),
                    'educator_review_required':True,'classroom_release_authorized':False,
                    'claim_boundary':'Source-owned item/memo alignment correction with mechanical artifact reconciliation only; no independent educator approval.'}
        (PACK/f'GRADE{grade:02d}_CONTENT_CORRECTION_20261102.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    grade3_assessment = json.loads((Path(SET['results'][2]['job_dir'])/'HOMS_GRADE_ASSESSMENT.json').read_text(encoding='utf-8'))
    grade3_geometry = next(q for q in grade3_assessment['sections'][0]['questions'] if q['number'] == '1.5')
    geometry_evidence = {'schema':'dio.homs.grade_exam_content_correction.v1','created_at':now,'grade':3,'question_id':'1.5',
                         'previous_prompt':'1.5 Name one 2-D shape with four equal sides and one object with that shape. [4]',
                         'updated_prompt':grade3_geometry['prompt'],
                         'reason':'The earlier version introduced equal-side quadrilaterals and rhombus alternatives that are not listed in the cited Grade 3 CAPS scope. The current prompt assesses a square or rectangle and the listed feature of straight sides.',
                         'corrected_exam_sha256':by_grade[3]['exam']['sha256'],'corrected_memo_sha256':by_grade[3]['memo']['sha256'],
                         'corrected_assessment_sha256':by_grade[3]['assessment_json_sha256'],
                         'question_mark_total':int(grade3_geometry['marks']),'memo_mark_total':sum(int(point['marks']) for point in grade3_geometry['memo']),
                         'caps_support_page':90,'educator_review_required':True,'classroom_release_authorized':False,
                         'claim_boundary':'Source-owned item scope correction bound to the official Grade 3 CAPS shapes page; no educator approval implied.'}
    (PACK/'GRADE03_GEOMETRY_SCOPE_CORRECTION_20261104.json').write_text(json.dumps(geometry_evidence,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    historical_geometry_path = PACK/'GRADE03_GEOMETRY_MEMO_CLARIFICATION_20261101.json'
    if historical_geometry_path.is_file():
        historical_geometry = json.loads(historical_geometry_path.read_text(encoding='utf-8'))
        historical_geometry['status'] = 'SUPERSEDED'
        historical_geometry['superseded_by'] = 'GRADE03_GEOMETRY_SCOPE_CORRECTION_20261104.json'
        historical_geometry['supersession_note'] = 'The current prompt asks for four straight sides and the memo accepts CAPS-listed squares or rectangles; it no longer asks for four equal sides or a rhombus.'
        historical_geometry_path.write_text(json.dumps(historical_geometry,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    grade10_assessment = json.loads((Path(SET['results'][9]['job_dir'])/'HOMS_GRADE_ASSESSMENT.json').read_text(encoding='utf-8'))
    grade10_questions = [q for q in grade10_assessment['sections'][0]['questions'] if q['number'] in ('1.1', '1.2')]
    reasoning_evidence = {'schema':'dio.homs.grade10_distance_speed_reasoning_correction.v1','created_at_utc':now,**GRADE10_REASONING_CORRECTION,
                          'question_ids':['1.1','1.2'],'corrected_exam_sha256':by_grade[10]['exam']['sha256'],
                          'corrected_memo_sha256':by_grade[10]['memo']['sha256'],'corrected_assessment_sha256':by_grade[10]['assessment_json_sha256'],
                          'question_mark_total':sum(int(q['marks']) for q in grade10_questions),
                          'memo_mark_total':sum(int(point['marks']) for q in grade10_questions for point in q['memo']),
                          'mechanical_moderation_state':moderation_by_grade[10]['mechanical_state'],
                          'educator_review_required':True,'classroom_release_authorized':False,
                          'claim_boundary':'Source-owned item/memo reasoning correction with mechanical artifact reconciliation only; no independent educator approval.'}
    (PACK/'GRADE10_DISTANCE_SPEED_REASONING_CORRECTION_20261102.json').write_text(json.dumps(reasoning_evidence,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    assessment = json.loads((Path(SET['results'][3]['job_dir'])/'HOMS_GRADE_ASSESSMENT.json').read_text(encoding='utf-8'))
    q4 = next(q for q in assessment['sections'][0]['questions'] if q['number'] == '1.3')
    fraction_evidence = {'schema':'dio.homs.grade_exam_content_correction.v1','created_at':now,**GRADE4_FRACTION_CORRECTION,
                         'corrected_exam_sha256':by_grade[4]['exam']['sha256'],'corrected_memo_sha256':by_grade[4]['memo']['sha256'],
                         'corrected_assessment_sha256':by_grade[4]['assessment_json_sha256'],
                         'question_mark_total':int(q4['marks']),'memo_mark_total':sum(int(point['marks']) for point in q4['memo']),
                         'educator_review_required':True,'classroom_release_authorized':False,
                         'claim_boundary':'Source-owned rubric clarity correction with mechanical artifact reconciliation only; no independent educator approval.'}
    (PACK/'GRADE04_FRACTION_MEMO_CORRECTION_20261102.json').write_text(json.dumps(fraction_evidence,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    capacity_item = next(q for q in assessment['sections'][0]['questions'] if q['number'] == '1.5')
    capacity_evidence = {'schema':'dio.homs.grade_exam_content_correction.v1','created_at':now,**GRADE4_CAPACITY_CORRECTION,
                         'corrected_exam_sha256':by_grade[4]['exam']['sha256'],'corrected_memo_sha256':by_grade[4]['memo']['sha256'],
                         'corrected_assessment_sha256':by_grade[4]['assessment_json_sha256'],
                         'question_mark_total':int(capacity_item['marks']),'memo_mark_total':sum(int(point['marks']) for point in capacity_item['memo']),
                         'caps_support_page':93,'educator_review_required':True,'classroom_release_authorized':False,
                         'claim_boundary':'Source-owned content/rubric scope correction bound to the official Grade 4 CAPS capacity-conversion page; no educator approval implied.'}
    (PACK/'GRADE04_CAPACITY_CONVERSION_CORRECTION_20261104.json').write_text(json.dumps(capacity_evidence,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    grade6_assessment = json.loads((Path(SET['results'][5]['job_dir'])/'HOMS_GRADE_ASSESSMENT.json').read_text(encoding='utf-8'))
    grade6_questions = [q for q in grade6_assessment['sections'][0]['questions'] if q['number'] in ('1.2', '1.3', '1.5')]
    grade6_evidence = {'schema':'dio.homs.grade_exam_content_correction.v1','created_at':now,'grade':6,
                       'question_ids':[q['number'] for q in grade6_questions],
                       'reason':'Reconciled prompt requirements with the one-mark criteria: the evening plan now explicitly requests time/order/rest; the peer-support item requests each element in its six-mark rubric; and screen-use evaluation requests benefits for both options plus one difficulty.',
                       'corrected_exam_sha256':by_grade[6]['exam']['sha256'],'corrected_memo_sha256':by_grade[6]['memo']['sha256'],
                       'corrected_assessment_sha256':by_grade[6]['assessment_json_sha256'],
                       'question_mark_total':sum(int(q['marks']) for q in grade6_questions),
                       'memo_mark_total':sum(int(point['marks']) for q in grade6_questions for point in q['memo']),
                       'per_question_prompt_and_memo':{q['number']:{'prompt':q['prompt'],'marks':int(q['marks']),'memo_points':len(q['memo'])} for q in grade6_questions},
                       'educator_review_required':True,'classroom_release_authorized':False,
                       'claim_boundary':'Source-owned prompt/rubric alignment correction; no educator approval implied.'}
    (PACK/'GRADE06_PROMPT_RUBRIC_ALIGNMENT_CORRECTION_20261104.json').write_text(json.dumps(grade6_evidence,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    title_correction_path = PACK / 'GRADE07_SOURCE_TITLE_CORRECTION_20261102.json'
    if title_correction_path.is_file():
        title_correction = json.loads(title_correction_path.read_text(encoding='utf-8'))
        title_correction.setdefault('rebound_artifacts', {}).update({
            'grade_exam_sha256': by_grade[7]['exam']['sha256'],
            'grade_memo_sha256': by_grade[7]['memo']['sha256'],
            'assessment_sha256': by_grade[7]['assessment_json_sha256'],
            'receipt_sha256': digest(Path(SET['results'][6]['job_dir']) / 'HOMS_GRADE_EXAM_RECEIPT.json'),
        })
        title_correction_path.write_text(json.dumps(title_correction,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'grade_packs':12,'grade2_prompt':CORRECTION['updated_prompt'],'grade2_marks':4,'memo_points':4,'all_docx_hashes_match_receipts':True,'all_grade_totals_reconcile':True,'release_authorized':False},indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())

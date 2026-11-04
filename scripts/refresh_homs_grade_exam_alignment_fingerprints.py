#!/usr/bin/env python3
"""Refresh the source-bound artifact hashes in the 12-grade CAPS question map."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "deliverables/homs_random_grade_exam_set_20261101"
ALIGNMENT = PACK / "CAPS_QUESTION_ALIGNMENT_ALL_GRADES_20261101.json"
SET_RECEIPT = PACK / "GRADE_EXAM_SET_RECEIPT.json"
PROMPT_REVISIONS = {
    (12, "1.1"): "1.1 The Consumer Protection Act is part of the Grade 12 CAPS topic on the impact of recent legislation. Using the ingredient information in the case, explain how this law could affect Koru's label decisions, state one check the owners should make before printing, and explain one possible effect of a misleading description. [8]",
    (10, "1.1"): "1.1 Distinguish distance and displacement, then calculate both for the trolley's first 6 s of motion. [8]",
    (10, "1.2"): "1.2 For the first 6 s, calculate the trolley's average velocity and average speed. State one difference between them. [9]",
    (4, "1.3"): "1.3 What fraction of the 192 seedlings is 48? Simplify it. Show how you simplify the fraction and check your answer. [6]",
    (7, "1.1"): "1.1 Classify these four items—fruit bought, cups bought, table fee, and money received from cups sold—as a production input, business expense, sales revenue, or all categories that apply. Explain why the fruit and table fee fit their categories. [6]",
    (3, "1.2"): "1.2 Use your total from Question 1.1 to put the bottle tops into bags of 6. Show a calculation or equal-groups drawing. State how many full bags you can make and whether any tops are left. [4]",
    (3, "1.5"): "1.5 Name one 2-D shape with four straight sides and one object with that shape. [4]",
    (4, "1.4"): "1.4 The class has 360 seeds and plants 145. Show the column subtraction, make any regrouping clear, and check your answer with addition. How many seeds remain? [7]",
    (4, "1.5"): "1.5 Each seedling needs 250 mL of water. For 8 seedlings, show the multiplication and the conversion calculation. Give the total in millilitres and litres. [6]",
    (10, "1.4"): "1.4 Assume the later acceleration stays constant at the value from Question 1.3 for a further 3 s, starting at +15 m·s⁻¹. Calculate the final velocity and signed displacement. Draw a velocity-time graph for this interval or show the trapezium area calculation, and state the direction. [11]",
    (5, "1.1"): "1.1 Name the four materials mixed in the example and name the processed material they make. [5]",
    (5, "1.2"): "1.2 Name one property to record for the starting materials before mixing and one property to record after the samples set. Explain why the class records both stages. [5]",
    (5, "1.3"): "1.3 In the two-sample test, identify what is changed, what is measured and three conditions that should be kept the same. Explain why this makes the comparison fair. [6]",
    (5, "1.4"): "1.4 Based on the planned test, predict which sample will support more counters, or predict that they will support the same number. Explain why your prediction is reasonable, state what result will count as evidence, and give one reason the result should be checked with repeated trials. [7]",
    (5, "1.5"): "1.5 Give suitable results-table headings, including units where needed, for the gravel test. Then describe two ways to keep the comparison reliable and one limitation of using small samples to choose material for a real path. [7]",
    (2, "1.4"): "1.4 Change this sentence to describe one pot: 'The pots are near a sunny window.' [4]",
    (11, "1.1"): "1.1 State the route problem. Give two details showing the conditions learners faced, and explain one reason the repair mattered. [8]",
    (8, "1.1"): "1.1 Explain how pressure from a friend could affect the learner’s confidence in their own ability. Write one positive self-talk statement and give one action that would help the learner use their own ability on the assignment. [6]",
    (4, "1.2"): "1.2 Learners measured the garden’s four sides with a tape: 8 m, 5 m, 8 m and 5 m. Add the four measurements to find the perimeter. [5]",
    (9, "1.1"): "1.1 Name three services the van offers and state where it stops each Thursday. [6]",
    (6, "1.1"): "1.1 Identify Thabo’s late-night habit and the activity he has stopped joining. State one effect in class and explain how his habit may contribute to it. [5]",
    (6, "1.2"): "1.2 Suggest a realistic evening plan with a time for homework, a screen-free period before bed and one sleep-preparation activity. Put the activities in a sensible order and explain how the plan could support rest. [5]",
    (6, "1.3"): "1.3 What could Thabo say to his friend? Write a respectful I-statement that names how he feels and why, asks for specific support, and names a trusted adult he could approach if the problem continues. Explain why asking for support is responsible. [6]",
    (6, "1.5"): "1.5 Suggest two realistic options Thabo could use to reduce late-night screen use. Give one benefit of each option, one possible difficulty with either option, and recommend one option using the scenario. [7]",
    (1, "1.3"): "1.3 After Nandi calls the teacher, name four safe, kind ways she can help her friend while waiting. [4]",
    (11, "1.3"): "1.3 Use the survey table to compare daily and occasional route use. Calculate the percentage in each group and write one accurate sentence describing what the figures show. [10]",
}
COVERAGE_REVISIONS = {
    (10, "1.1"): "Uses a stated reversal and three positions to distinguish total path length (distance) from the directed change in position (displacement), then calculates each.",
    (10, "1.2"): "Calculates average velocity from signed displacement and average speed from total distance over the same time interval, then explains the directional distinction.",
    (4, "1.3"): "Forms 48/192, simplifies by dividing numerator and denominator by a common factor, and checks that one quarter of 192 is 48.",
    (7, "1.1"): "Distinguishes a material used to make the fruit cups from a business expense while recognizing the fruit purchase is both; classifies the table fee as an expense for market selling space.",
    (3, "1.2"): "Uses the previous item total to model equal groups of six, calculates quotient and remainder consistently with the learner's carried-forward total, and reports bags and unused tops; award method and result credit for consistent follow-through.",
    (3, "1.5"): "Identifies a square or rectangle from the Grade 3 CAPS list, describes its four straight sides, and gives an object with that flat shape.",
    (4, "1.5"): "Multiplies 250 mL by 8, then applies the Grade 4 CAPS relationship between litres and millilitres to express 2,000 mL as 2 L.",
    (4, "1.4"): "Uses a written three-digit subtraction with visible regrouping, place-value subtraction and an inverse addition check; marks now correspond to the requested calculation and verification steps.",
    (10, "1.4"): "Uses the later acceleration from Question 1.3 over a stated further 3 s, calculates final velocity, and finds signed displacement by drawing the data-based velocity-time trapezium or showing its area calculation; no pre-drawn graph is assumed.",
    (11, "1.1"): "Identifies the muddy, slippery route from the passage, cites its location and duration/condition after rain, and explains the safety or access reason for repair; survey-table figures are assessed separately in Question 1.3.",
    (8, "1.1"): "Uses the passage’s friend/peer pressure as an influence on self-concept, then applies Grade 8 Term 1 positive self-talk and a strategy to extend personal potential.",
    (4, "1.2"): "Uses tape-measured side lengths and addition to find the garden perimeter, matching the Grade 4 measurement skill without requiring a perimeter formula.",
    (9, "1.1"): "Retrieves three explicit services plus the stopping location and weekly day from the Grade 9 reading stimulus.",
    (6, "1.1"): "Assesses late video use, sleeping late, stopped play and tiredness using the Grade 6 Term 2 self-management topic; the memo ties one habit to its classroom effect.",
    (1, "1.3"): "Assesses age-appropriate safety and care while an adult responds, without rescoring the teacher call already stated in the scenario.",
    (8, "1.1"): "Applies the Grade 8 Term 1 CAPS scope for friends and peers influencing self-concept, positive self-talk, and strategies to extend personal potential; assignment details are the original source-based scenario.",
    (2, "1.4"): "Applies Grade 2 plural forms and the verb to be in a simple present-tense sentence, with singular noun agreement and sentence punctuation.",
    (11, "1.3"): "Reads and compares categories in a printed survey table, calculates both proportions, and states what the figures show; the case is a source-bound visual-text exercise, not a claim that the survey represents all learners.",
}
CAPS_TOPIC_REVISIONS = {
    (12, "1.1"): "Grade 12 Term 1: Macro environment — impact of recent legislation on business; Consumer Protection Act",
    (10, "1.2"): "Grade 10 motion in one dimension: average speed and average velocity",
    (4, "1.5"): "Grade 4 Term 3 capacity/volume: solve a capacity problem and convert between millilitres and litres",
    (7, "1.4"): "Grade 7 financial literacy: income, expenses and profit; entrepreneurship and Entrepreneur’s Day stock decisions",
    (10, "1.4"): "Grade 10 motion in one dimension: constant acceleration and signed displacement from a velocity-time graph",
    (5, "1.1"): "Grade 5 Term 2 processing materials: mixing sand, gravel, cement and water to make concrete",
    (5, "1.2"): "Grade 5 Term 2 processing materials: recording and comparing properties before and after processing",
    (5, "1.3"): "Grade 5 investigation skills applied to processing materials: planning a fair comparison",
    (5, "1.4"): "Grade 5 investigation skills and processed material properties: predicting and evaluating results",
    (5, "1.5"): "Grade 5 investigation skills: recording results, repeating trials and evaluating a processed material",
}
COVERAGE_REVISIONS.update({
    (5, "1.1"): "Identifies the four ingredients and concrete product named in the Grade 5 CAPS processing-materials example.",
    (5, "1.2"): "Records observable properties of starting materials and set concrete, then compares before/after properties as required for processing materials.",
    (5, "1.3"): "Applies the Grades 4–6 fair-test skill to the CAPS concrete example by varying gravel amount, measuring counter support before cracking, and controlling other conditions.",
    (5, "1.4"): "Uses the Grades 4–6 predicting, investigating and repeating skills to evaluate a stated comparison of two processed concrete samples; no outcome is asserted in advance.",
    (5, "1.5"): "Records and compares results from a repeatable processing-material test and recognizes the limit of extrapolating small-sample results to a full path.",
})
CAPS_PAGE_REPLACEMENTS = {
    (12, "1.1"): [(38, ["Grade 12", "Macro environment", "impact of recent legislation", "Consumer Protection Act"])],
    (5, "1.1"): [(42, ["processing materials", "concrete"])],
    (5, "1.2"): [(42, ["processing materials", "properties before and after"])],
    (5, "1.3"): [(17, ["fair test", "investigations"]), (42, ["concrete", "processing materials"])],
    (5, "1.4"): [(17, ["predicting", "repeated"]), (43, ["strong", "durable"])],
    (5, "1.5"): [(17, ["recording information", "repeated"]), (42, ["recording and comparing", "processed materials"])],
}
CAPS_PAGE_ADDITIONS = {
    (10, "1.4"): {"page_text_sha256": "pending-recompute", "physical_pdf_page": 62, "topic_terms_found": ["motion"]},
    (7, "1.4"): {"page_text_sha256": "pending-recompute", "physical_pdf_page": 18, "topic_terms_found": ["income", "expenses", "profit"]},
    (4, "1.5"): {"page_text_sha256": "pending-recompute", "physical_pdf_page": 93, "topic_terms_found": ["Grade 4 learners", "Convert between litres and millilitres"]},
}
COVERAGE_REVISIONS.update({
    (12, "1.1"): "Applies the Grade 12 Term 1 macro-environment unit on the impact of recent legislation to Koru's ingredient label, using the Consumer Protection Act and a source-based requirement to avoid misleading trade descriptions.",
    (7, "1.4"): "Connects unsold inventory, next-market stock planning, sales revenue and profit to Grade 7 Term 2 income/expenses/profit plus Term 3 buying/selling/profit and Entrepreneur’s Day; the practical freshness/safety considerations remain a case application.",
})


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    alignment = json.loads(ALIGNMENT.read_text(encoding="utf-8"))
    set_receipt = json.loads(SET_RECEIPT.read_text(encoding="utf-8"))
    rows = {int(row["grade"]): row for row in alignment["grades"]}
    if len(rows) != 12 or set(rows) != set(range(1, 13)):
        raise ValueError("CAPS question alignment must contain exactly one row for each grade")
    corpus = json.loads((ROOT / "corpora/caps/caps_corpus_manifest.json").read_text(encoding="utf-8"))
    page_cache = {}
    reconciled = []
    refreshed = []
    prompt_revisions = []
    revised_keys = set()
    for entry in set_receipt["results"]:
        grade = int(entry["grade"])
        folder = Path(entry["job_dir"])
        if not folder.is_absolute():
            folder = ROOT / folder
        receipt = json.loads((folder / "HOMS_GRADE_EXAM_RECEIPT.json").read_text(encoding="utf-8"))
        assessment_path = folder / "HOMS_GRADE_ASSESSMENT.json"
        assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
        row = rows[grade]
        question_by_id = {
            str(question.get("number") or ""): str(question.get("prompt") or "")
            for section in assessment.get("sections") or []
            for question in section.get("questions") or []
        }
        mappings = row.get("question_mappings") or []
        mapped = {str(item.get("question_id") or ""): item for item in mappings}
        if len(question_by_id) != 5 or len(mapped) != 5 or set(question_by_id) != set(mapped):
            raise ValueError(f"Grade {grade}: CAPS question map does not exactly cover current source question IDs")
        for question_id, prompt in question_by_id.items():
            mapping = mapped[question_id]
            old_prompt = str(mapping.get("prompt") or "")
            if old_prompt == prompt:
                continue
            key = (grade, question_id)
            if PROMPT_REVISIONS.get(key) != prompt:
                raise ValueError(f"Grade {grade} question {question_id}: unexpected prompt change")
            mapping["prompt"] = prompt
            prompt_revisions.append({"grade": grade, "question_id": question_id, "previous_prompt": old_prompt, "updated_prompt": prompt})
            revised_keys.add(key)
        for (revision_grade, question_id), coverage in COVERAGE_REVISIONS.items():
            if grade == revision_grade:
                mapped[question_id]["coverage_link"] = coverage
        for (revision_grade, question_id), topic in CAPS_TOPIC_REVISIONS.items():
            if grade == revision_grade:
                mapped[question_id]["caps_topic"] = topic
        for (revision_grade, question_id), page in CAPS_PAGE_ADDITIONS.items():
            if grade == revision_grade:
                pages = mapped[question_id].setdefault("caps_pages", [])
                if not any(item.get("physical_pdf_page") == page["physical_pdf_page"] for item in pages):
                    pages.append(dict(page))
        source_match = next((doc for doc in corpus.get("documents", []) if doc.get("sha256") == row.get("caps_source_sha256")), None)
        if source_match is None:
            raise ValueError(f"Grade {grade}: source PDF missing from CAPS corpus manifest")
        source_paths = [path for path in (ROOT / "corpora/caps/pdf").rglob(Path(source_match["path"]).name) if sha(path) == row["caps_source_sha256"]]
        if len(source_paths) != 1:
            raise ValueError(f"Grade {grade}: expected one hash-matched CAPS PDF, found {len(source_paths)}")
        for question_id, mapping in mapped.items():
            for citation in mapping.get("caps_pages") or []:
                page = int(citation["physical_pdf_page"])
                cache_key = (str(source_paths[0]), page)
                if cache_key not in page_cache:
                    extracted = subprocess.run(["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(source_paths[0]), "-"], check=True, capture_output=True, text=True).stdout.strip()
                    if not extracted:
                        raise ValueError(f"Grade {grade} CAPS page {page} has no extracted text")
                    page_cache[cache_key] = hashlib.sha256(extracted.encode("utf-8")).hexdigest()
                old = str(citation.get("page_text_sha256") or "")
                new = page_cache[cache_key]
                reconciled.append({"grade": grade, "question_id": question_id, "physical_pdf_page": page, "old_sha256": old, "new_sha256": new})
                citation["page_text_sha256"] = new
        for (revision_grade, question_id), replacement_pages in CAPS_PAGE_REPLACEMENTS.items():
            if grade == revision_grade:
                source_match_for_pages = next((doc for doc in corpus.get("documents", []) if doc.get("sha256") == row.get("caps_source_sha256")), None)
                if source_match_for_pages is None:
                    raise ValueError(f"Grade {grade}: source PDF missing while replacing question citations")
                matches_for_pages = [path for path in (ROOT / "corpora/caps/pdf").rglob(Path(source_match_for_pages["path"]).name) if sha(path) == row["caps_source_sha256"]]
                if len(matches_for_pages) != 1:
                    raise ValueError(f"Grade {grade}: expected one byte-verified CAPS PDF for replacement citations")
                citations = []
                for page_number, terms in replacement_pages:
                    text_value = subprocess.run(["pdftotext", "-layout", "-f", str(page_number), "-l", str(page_number), str(matches_for_pages[0]), "-"], check=True, capture_output=True, text=True).stdout.strip()
                    citations.append({"physical_pdf_page": page_number, "page_text_sha256": hashlib.sha256(text_value.encode("utf-8")).hexdigest(), "topic_terms_found": terms})
                mapped[question_id]["caps_pages"] = citations
        if (row.get("grade") != grade or row.get("subject") != assessment.get("subject")
                or row.get("caps_source_sha256") != receipt.get("caps_source", {}).get("sha256")):
            raise ValueError(f"Grade {grade}: CAPS question map identity differs from the current source receipt")
        for role, filename in (("exam", "GRADE_EXAM.docx"), ("memo", "GRADE_MEMO.docx"), ("json", "HOMS_GRADE_ASSESSMENT.json")):
            artifact = folder / filename
            actual = sha(artifact)
            if actual != receipt.get("assessment", {}).get(role, {}).get("sha256"):
                raise ValueError(f"Grade {grade}: {role} artifact differs from its grade receipt")
            row[f"{role}_sha256"] = actual
        row["assessment_json_sha256"] = sha(assessment_path)
        refreshed.append({"grade": grade, "exam_sha256": row["exam_sha256"], "memo_sha256": row["memo_sha256"]})
    alignment["artifact_fingerprints_refreshed_after_renderer_revision"] = True
    if not revised_keys.issubset(PROMPT_REVISIONS):
        raise ValueError(f"Unexpected question prompt revisions were detected: {sorted(revised_keys - set(PROMPT_REVISIONS))}")
    alignment["artifact_fingerprint_refresh"] = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "reason": "Grade 6 question-to-rubric alignment for evening planning, help-seeking and option evaluation; Grade 5 rubric fairness and before/after prompt corrections; Grade 4 capacity-conversion scope, method and mark-allocation correction; Grade 3 geometry scope and carry-forward memo corrections, Grade 2 grammar item scope correction, Grade 1 safety question/memo scope correction, Grade 6 self-management question/memo precision correction, Grade 9 question/memo response-count correction, Grade 4 perimeter assessment method correction, Grade 8 self-concept and peer-influence alignment correction, Grade 11 Q1.1 memo/passage evidence correction, Grade 5 item/source correction, Grade 7 financial-literacy source trace refinement, and reconciliation of every cited CAPS page-text hash against pdftotext -layout output from the byte-verified official PDF.",
        "prompt_revisions": prompt_revisions,
        "grades": refreshed,
        "caps_page_hash_reconciliation": {"method": "pdftotext -layout per physical page; trim outer whitespace; UTF-8 SHA-256", "citation_count": len(reconciled), "changed_count": sum(item["old_sha256"] != item["new_sha256"] for item in reconciled), "citations": reconciled},
    }
    ALIGNMENT.write_text(json.dumps(alignment, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"grade_count": len(refreshed), "all_prompt_maps_match": True, "page_citation_count": len(reconciled), "page_hashes_changed": sum(item["old_sha256"] != item["new_sha256"] for item in reconciled), "all_page_hashes_reconciled": True, "alignment": ALIGNMENT.relative_to(ROOT).as_posix()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

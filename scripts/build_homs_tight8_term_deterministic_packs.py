#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from apply_homs_design_law import (  # noqa: E402
    DEFAULT_ASSESSMENT_DESIGN,
    DEFAULT_DESIGN_LAW,
    apply_design_law,
    assessment_design_for_pack,
    load_json as load_design_json,
    render_docx,
)
from attach_homs_source_assets import DEFAULT_BANK as DEFAULT_SOURCE_BANK, attach_sources  # noqa: E402
from build_homs_tight8_term_contextual_packs import TERM_FOCI, TIGHT8  # noqa: E402
from run_hymark_exam_builder import (  # noqa: E402
    load_subject_profile,
    sum_question_marks,
    sum_rubric_marks,
    validate_assessment_pack,
)


DEFAULT_OUT = ROOT / "deliverables" / "homs_tight8_term_deterministic_packs"

SUBJECT_META = {
    "english_language": ("English Language", "fet.english_language", "language_integrated_assessment", "English"),
    "afrikaans_language": ("Afrikaans Language", "fet.afrikaans_language", "language_integrated_assessment", "Afrikaans"),
    "life_orientation": ("Life Orientation", "fet.life_orientation", "case_study_structured_questions", "English"),
    "mathematics": ("Mathematics", "fet.mathematics", "calculation_problem_solving", "English"),
    "physical_sciences": ("Physical Sciences", "fet.physical_sciences", "data_diagram_practical_investigation", "English"),
    "life_sciences": ("Life Sciences", "fet.life_sciences", "data_diagram_practical_investigation", "English"),
    "geography": ("Geography", "fet.geography", "source_based_plus_extended_response", "English"),
    "history": ("History", "fet.history", "source_based_plus_essay", "English"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_") or "item"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def visual_blueprint(subject_id: str, subject: str, term: str, profile_id: str, family: str, focus: dict[str, str]) -> dict[str, Any]:
    kinds_by_family = {
        "language_integrated_assessment": [{"id": "language_response_planner", "title": "Text response and language planner", "role": "learner_workspace", "visual_kind": "language_planner"}],
        "case_study_structured_questions": [{"id": "case_decision_table", "title": "Case facts and decision table", "role": "stimulus_and_workspace", "visual_kind": "case_table"}],
        "calculation_problem_solving": [
            {"id": "working_grid", "title": "Working grid with method mark space", "role": "learner_workspace", "visual_kind": "working_grid"},
            {"id": "axis_or_diagram", "title": "Axis, diagram or table required by the topic", "role": "stimulus_or_workspace", "visual_kind": "axis_diagram"},
        ],
        "data_diagram_practical_investigation": [
            {"id": "science_data_or_graph", "title": "Science data table or graph stimulus", "role": "stimulus", "visual_kind": "data_table"},
            {"id": "science_diagram", "title": "Science labelled diagram stimulus", "role": "stimulus", "visual_kind": "axis_diagram"},
            {"id": "investigation_method_data", "title": "Investigation method and data sheet", "role": "stimulus_and_workspace", "visual_kind": "investigation_sheet"},
        ],
        "source_based_plus_extended_response": [
            {"id": "geo_map_extract", "title": "Map extract with legend, scale, north arrow and labelled features", "role": "stimulus", "visual_kind": "map_extract"},
            {"id": "geo_data_table_or_graph", "title": "Geography data table or graph", "role": "stimulus", "visual_kind": "data_table"},
        ],
        "source_based_plus_essay": [
            {"id": "source_provenance_panel", "title": "Source provenance panel", "role": "stimulus", "visual_kind": "source_extract"},
            {"id": "claim_evidence_reasoning_table", "title": "Claim-evidence-reasoning table", "role": "learner_workspace", "visual_kind": "evidence_table"},
        ],
    }
    return {
        "schema": "knowedge.homs_visual_blueprint.v1",
        "subject": subject,
        "grade": 12,
        "phase": "fet_grade_10_12",
        "term": term,
        "canonical_profile_id": profile_id,
        "assessment_family": family,
        "render_shell": "language_integrated_task" if family == "language_integrated_assessment" else "question_paper",
        "assessment_content_focus": list(focus.values()),
        "required_visuals": kinds_by_family.get(family, []),
        "generation_constraints": [
            "Every question must be answerable from the stated term focus, supplied stimulus and grade-appropriate subject knowledge.",
            "Mark totals must reconcile exactly.",
            "Educator approval is required before classroom use.",
        ],
    }


def q(number: str, question: str, marks: int, memo: list[str]) -> dict[str, Any]:
    return {"number": number, "question": question, "marks": marks, "memo": memo}


def language_sections(subject_id: str, focus: dict[str, str]) -> list[dict[str, Any]]:
    af = subject_id == "afrikaans_language"
    if af:
        return [
            {
                "title": "Afdeling A: Begrip En Visuele Geletterdheid",
                "mode": "source_response",
                "instructions": "Lees die bron- en visuele stimulus noukeurig en beantwoord die vrae in Afrikaans.",
                "stimulus": f"Bronstel oor {focus['focus']} en {focus['secondary_focus']}. Die opvoeder voeg die goedgekeurde teks, spotprent, advertensie of infografika by.",
                "questions": [
                    q("1.1", "Identifiseer die hoofgedagte van die teks en haal EEN bewys uit die bron aan.", 4, ["Hoofgedagte korrek.", "Bewys uit die bron pas by die hoofgedagte."]),
                    q("1.2", "Verduidelik hoe toon en register die teikengroep beinvloed.", 6, ["Verwys na toon.", "Verwys na register.", "Koppel aan teikengroep."]),
                    q("1.3", "Ontleed die visuele boodskap en verduidelik hoe beeld en woorde saam betekenis skep.", 8, ["Noem visuele tegniek.", "Noem taalkeuse.", "Verduidelik gesamentlike effek."]),
                    q("1.4", "Skryf 'n kort opsomming van die kerninligting in 60-80 woorde.", 7, ["Kernpunte gekies.", "Geen onnodige besonderhede.", "Woordtelling en eie woorde."]),
                ],
            },
            {
                "title": "Afdeling B: Taal In Konteks",
                "mode": "language_structures",
                "instructions": "Gebruik die bronteks vir taalstruktuur- en redigeringsvrae.",
                "stimulus": f"Taalfokus: {focus['methodology_focus']}.",
                "questions": [
                    q("2.1", "Verbeter die gegewe sin deur woordkeuse, leestekens en register te korrigeer.", 5, ["Korrekte woordkeuse.", "Korrekte leestekens.", "Register bly gepas."]),
                    q("2.2", "Verduidelik die funksie van TWEE taalstrukture in die teks.", 5, ["Twee strukture genoem.", "Funksies akkuraat verduidelik."]),
                    q("2.3", "Herskryf 'n sin in 'n meer formele register sonder om die betekenis te verander.", 5, ["Betekenis behou.", "Formele register konsekwent."]),
                ],
            },
            {
                "title": "Afdeling C: Skryfrespons",
                "mode": "writing_response",
                "instructions": "Beplan en skryf 'n gestruktureerde respons.",
                "stimulus": f"Skryfopdrag: {focus['extended_focus']}.",
                "questions": [
                    q("3.1", "Skryf 'n beplande transaksionele teks met gepaste struktuur, register en doel.", 10, ["Struktuur pas by tekssoort.", "Register en doel is duidelik.", "Inhoud is samehangend."]),
                ],
            },
        ]
    return [
        {
            "title": "Section A: Comprehension And Visual Literacy",
            "mode": "source_response",
            "instructions": "Read the supplied text and visual stimulus carefully before answering.",
            "stimulus": f"Source set on {focus['focus']} and {focus['secondary_focus']}. The educator inserts the approved text, cartoon, advertisement or infographic.",
            "questions": [
                q("1.1", "Identify the main idea of the text and quote ONE piece of supporting evidence.", 4, ["Main idea is accurate.", "Evidence is quoted or paraphrased from the source."]),
                q("1.2", "Explain how tone and register shape the reader's response.", 6, ["Tone identified.", "Register discussed.", "Effect on reader explained."]),
                q("1.3", "Analyse how the visual text uses image, layout and wording to communicate its message.", 8, ["Image/layout discussed.", "Wording discussed.", "Message explained."]),
                q("1.4", "Write a 60-80 word summary of the key information.", 7, ["Relevant points selected.", "Own words used.", "Word limit controlled."]),
            ],
        },
        {
            "title": "Section B: Language In Context",
            "mode": "language_structures",
            "instructions": "Use the source text for language and editing questions.",
            "stimulus": f"Language focus: {focus['methodology_focus']}.",
            "questions": [
                q("2.1", "Edit the supplied sentence for diction, punctuation and register.", 5, ["Diction improved.", "Punctuation corrected.", "Register remains appropriate."]),
                q("2.2", "Explain the function of TWO language structures used in the text.", 5, ["Two structures identified.", "Functions explained accurately."]),
                q("2.3", "Rewrite a sentence in a more formal register without changing the meaning.", 5, ["Meaning retained.", "Formal register consistent."]),
            ],
        },
        {
            "title": "Section C: Writing Response",
            "mode": "writing_response",
            "instructions": "Plan and write a structured response.",
            "stimulus": f"Writing task: {focus['extended_focus']}.",
            "questions": [
                q("3.1", "Write a transactional text with suitable structure, register and purpose.", 10, ["Structure suits text type.", "Register and purpose are clear.", "Content is coherent."]),
            ],
        },
    ]


def generic_sections(subject_id: str, focus: dict[str, str]) -> list[dict[str, Any]]:
    if subject_id == "mathematics":
        return [
            {"title": "Section A: Concepts And Procedures", "mode": "calculation", "instructions": "Show all working.", "stimulus": f"Topic focus: {focus['focus']}.", "questions": [
                q("1.1", "Solve a routine problem linked to the stated term focus and show all algebraic working.", 6, ["Correct method.", "Accurate simplification.", "Final answer stated."]),
                q("1.2", "Interpret the supplied graph, table or diagram and state the meaning of one key feature.", 6, ["Feature identified.", "Mathematical meaning explained."]),
                q("1.3", "Complete a multi-step calculation using the supplied values and units.", 8, ["Values substituted.", "Steps logical.", "Answer with unit."]),
            ]},
            {"title": "Section B: Problem Solving", "mode": "structured_problem", "instructions": "Use the workspace and justify each step.", "stimulus": f"Problem context: {focus['secondary_focus']}.", "questions": [
                q("2.1", "Set up and solve a non-routine problem from the term context.", 10, ["Correct representation.", "Valid strategy.", "Accurate conclusion."]),
                q("2.2", "Justify one method step or proof statement.", 5, ["Relevant theorem/rule.", "Reasoning clear."]),
            ]},
            {"title": "Section C: Integrated Application", "mode": "application", "instructions": "Combine concepts from the term pack.", "stimulus": f"Integrated focus: {focus['extended_focus']}.", "questions": [
                q("3.1", "Answer an integrated application question and comment on the reasonableness of the result.", 15, ["Correct plan.", "Accurate working.", "Reasonableness comment."]),
            ]},
        ]
    if subject_id == "life_orientation":
        return [
            {"title": "Section A: Scenario Analysis", "mode": "case_response", "instructions": "Use the scenario and respond with practical judgement.", "stimulus": f"Scenario: A Grade 12 learner faces choices linked to {focus['focus']}.", "questions": [
                q("1.1", "Identify the main issue in the scenario and explain why it matters.", 5, ["Issue identified.", "Importance explained."]),
                q("1.2", "Discuss TWO possible consequences of an unhealthy or irresponsible choice.", 6, ["Two consequences.", "Clear explanation."]),
                q("1.3", "Recommend TWO support strategies and justify each one.", 8, ["Two strategies.", "Justification linked to scenario."]),
            ]},
            {"title": "Section B: Decision And Reflection", "mode": "reflection", "instructions": "Keep reflection appropriate and non-private.", "stimulus": f"Reflection focus: {focus['methodology_focus']}.", "questions": [
                q("2.1", "Evaluate a responsible decision using evidence from the scenario.", 8, ["Decision evaluated.", "Scenario evidence used."]),
                q("2.2", "Create a brief action plan with three safe, realistic steps.", 8, ["Three steps.", "Steps realistic and safe."]),
            ]},
            {"title": "Section C: Portfolio Evidence", "mode": "portfolio_response", "instructions": "Complete the supervised evidence item.", "stimulus": f"Portfolio focus: {focus['extended_focus']}.", "questions": [
                q("3.1", "Complete a portfolio entry showing what evidence an educator can assess.", 15, ["Evidence is observable.", "Reflection is relevant.", "Plan is practical."]),
            ]},
        ]
    if subject_id in {"physical_sciences", "life_sciences"}:
        return [
            {"title": "Section A: Concepts And Data", "mode": "data_response", "instructions": "Use the supplied data, diagram or graph.", "stimulus": f"Data/diagram stimulus linked to {focus['focus']}.", "questions": [
                q("1.1", "Define one key concept from the term focus.", 2, ["Definition scientifically accurate."]),
                q("1.2", "Describe the trend or relationship shown by the supplied data.", 5, ["Trend described.", "Evidence cited."]),
                q("1.3", "Explain the process or principle using correct terminology.", 8, ["Correct terms.", "Logical explanation."]),
                q("1.4", "Calculate or infer a result from the supplied values and show working where needed.", 5, ["Working shown.", "Answer accurate."]),
            ]},
            {"title": "Section B: Investigation Design", "mode": "investigation", "instructions": "Critique method, variables and evidence.", "stimulus": f"Investigation focus: {focus['methodology_focus']}.", "questions": [
                q("2.1", "State a suitable aim or hypothesis for the investigation.", 3, ["Aim/hypothesis testable."]),
                q("2.2", "Identify independent, dependent and controlled variables.", 6, ["Variables correctly classified."]),
                q("2.3", "Evaluate validity and reliability and suggest one improvement.", 6, ["Validity/reliability explained.", "Improvement practical."]),
            ]},
            {"title": "Section C: Application", "mode": "application", "instructions": "Use subject knowledge and supplied evidence.", "stimulus": f"Application focus: {focus['extended_focus']}.", "questions": [
                q("3.1", "Answer an integrated explanation question using evidence from the stimulus.", 15, ["Evidence used.", "Explanation coherent.", "Conclusion supported."]),
            ]},
        ]
    if subject_id == "geography":
        return [
            {"title": "Section A: Map And Source Skills", "mode": "source_response", "instructions": "Use the supplied map, photograph, diagram or graph.", "stimulus": f"Geography source set linked to {focus['focus']}.", "questions": [
                q("1.1", "Identify TWO visible spatial patterns or features from the source.", 4, ["Two features identified."]),
                q("1.2", "Explain the process or relationship shown in the source.", 8, ["Process explained.", "Source evidence cited."]),
                q("1.3", "Interpret the supplied data table or graph and describe the trend.", 6, ["Trend described.", "Data cited."]),
            ]},
            {"title": "Section B: Geographic Explanation", "mode": "extended_response", "instructions": "Write structured geographical explanations.", "stimulus": f"Explanation focus: {focus['secondary_focus']}.", "questions": [
                q("2.1", "Compare two places, processes or patterns using source evidence.", 8, ["Comparison clear.", "Evidence used."]),
                q("2.2", "Suggest a sustainable response to the geographic challenge.", 9, ["Response relevant.", "Reasoning justified."]),
            ]},
            {"title": "Section C: Integrated Mapwork Or GIS", "mode": "application", "instructions": "Apply spatial reasoning.", "stimulus": f"Integrated focus: {focus['extended_focus']}.", "questions": [
                q("3.1", "Complete an integrated spatial reasoning task using map/data evidence.", 15, ["Map/data evidence used.", "Reasoning accurate."]),
            ]},
        ]
    if subject_id == "history":
        return [
            {"title": "Section A: Source-Based Questions", "mode": "source_response", "instructions": "Use the supplied historical source set.", "stimulus": f"Source set on {focus['focus']}. Each source must include provenance.", "questions": [
                q("1.1", "Contextualise the source in relation to the historical topic.", 4, ["Context accurate."]),
                q("1.2", "Explain the message or viewpoint of the source using evidence.", 6, ["Viewpoint explained.", "Evidence cited."]),
                q("1.3", "Evaluate the usefulness or reliability of the source.", 8, ["Provenance considered.", "Limitation discussed."]),
            ]},
            {"title": "Section B: Comparison And Causation", "mode": "evidence_response", "instructions": "Compare evidence and explain causation.", "stimulus": f"Evidence focus: {focus['methodology_focus']}.", "questions": [
                q("2.1", "Compare two sources and explain where they agree or differ.", 8, ["Agreement/difference clear.", "Evidence from both sources."]),
                q("2.2", "Explain one cause and one consequence linked to the topic.", 9, ["Cause explained.", "Consequence explained."]),
            ]},
            {"title": "Section C: Essay Paragraph", "mode": "extended_response", "instructions": "Write a concise, evidence-linked argument.", "stimulus": f"Essay focus: {focus['extended_focus']}.", "questions": [
                q("3.1", "Write a structured historical paragraph with a clear claim, evidence and judgement.", 15, ["Claim clear.", "Evidence relevant.", "Judgement sustained."]),
            ]},
        ]
    raise ValueError(f"No deterministic template for {subject_id}")


def rubric_for(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = sum(int(q["marks"]) for s in sections for q in s["questions"])
    return [
        {"criterion": "Subject accuracy and terminology", "marks": total // 4, "descriptor": "Uses accurate concepts and terminology."},
        {"criterion": "Evidence, data or source use", "marks": total // 4, "descriptor": "Uses supplied evidence appropriately."},
        {"criterion": "Reasoning and explanation", "marks": total // 4, "descriptor": "Shows logical, grade-appropriate reasoning."},
        {"criterion": "Communication and completion", "marks": total - 3 * (total // 4), "descriptor": "Answers are clear, complete and structured."},
    ]


def build_pack(subject_id: str, term: str) -> dict[str, Any]:
    subject, profile_id, family, language = SUBJECT_META[subject_id]
    focus = TERM_FOCI[subject_id][term]
    sections = language_sections(subject_id, focus) if subject_id in {"english_language", "afrikaans_language"} else generic_sections(subject_id, focus)
    title_subject = "Afrikaans" if subject_id == "afrikaans_language" else subject
    pack = {
        "schema": "knowedge.homs_assessment_pack.v1",
        "subject": title_subject,
        "language_of_assessment": language,
        "grade": 12,
        "phase": "fet_grade_10_12",
        "assessment_title": f"{title_subject} Grade 12 Term {term} Controlled Assessment Pack",
        "canonical_profile_id": profile_id,
        "blueprint": family,
        "render_shell": "language_integrated_task" if family == "language_integrated_assessment" else "question_paper",
        "duration": "1 hour",
        "total_marks": 50,
        "visual_blueprint": visual_blueprint(subject_id, subject, term, profile_id, family, focus),
        "sections": sections,
        "rubric": rubric_for(sections),
        "teacher_review_checklist": [
            "Confirm CAPS term and topic fit before classroom use.",
            "Insert or approve final source material where the pack requests educator-supplied sources.",
            "Check mark allocation, memo wording and learner level.",
            "Confirm visuals are suitable and not treated as official source material unless sourced separately.",
        ],
        "generation_backend": "deterministic_caps_term_template_with_provider_enrichment_ready",
    }
    return pack


def convert_pdf(docx_path: Path, out_dir: Path) -> Path | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(docx_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    pdf_path = out_dir / f"{docx_path.stem}.pdf"
    return pdf_path if result.returncode == 0 and pdf_path.exists() else None


def zip_dir(source: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source.rglob("*"):
            if path.is_file() and path.resolve() != target.resolve():
                zf.write(path, path.relative_to(source))


def build_one(subject_id: str, term: str, out_root: Path) -> dict[str, Any]:
    job_dir = out_root / f"deterministic-{subject_id}-g12-t{term}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    job_dir.mkdir(parents=True, exist_ok=True)
    pack = build_pack(subject_id, term)
    write_json(job_dir / "assessment_pack.json", pack)

    source_receipt = attach_sources(
        job_dir=job_dir,
        bank_path=Path(DEFAULT_SOURCE_BANK).expanduser().resolve(),
        explicit_subject=subject_id,
        explicit_types=None,
        limit=3,
        dry_run=False,
    )
    pack = load_design_json(job_dir / "assessment_pack.json")
    pack.setdefault("source_embedding", {})
    pack["source_embedding"]["generated_visual_policy"] = "suppress_generated_visuals_when_source_assets_present"
    write_json(job_dir / "assessment_pack.json", pack)

    request = {"total_marks": 50, "visual_blueprint": pack["visual_blueprint"], "subject_profile": load_subject_profile(subject_id), "term": term}
    errors = validate_assessment_pack(pack, request)
    design_receipt = apply_design_law(job_dir, DEFAULT_DESIGN_LAW, DEFAULT_ASSESSMENT_DESIGN)
    design_law = load_design_json(DEFAULT_DESIGN_LAW)
    design_payload = load_design_json(DEFAULT_ASSESSMENT_DESIGN)
    assessment_design = assessment_design_for_pack(pack, design_payload)
    learner_docx = render_docx(job_dir, pack, design_law, design_receipt.get("assets") or [], assessment_design, include_memo_sections=False, output_name="ASSESSMENT_LEARNER.docx")
    learner_pdf = convert_pdf(learner_docx, job_dir / "pdf_check")
    review_pdf = convert_pdf(Path(design_receipt["formatted_docx"]), job_dir / "pdf_check")
    zip_path = job_dir / "HOMS_DETERMINISTIC_TERM_PACK.zip"
    zip_dir(job_dir, zip_path)
    receipt = {
        "schema": "knowedge.homs_deterministic_term_pack_receipt.v1",
        "created_at": utc_now(),
        "status": "passed" if not errors else "failed_validation",
        "subject_id": subject_id,
        "subject": pack["subject"],
        "grade": 12,
        "term": term,
        "question_marks": sum_question_marks(pack),
        "rubric_marks": sum_rubric_marks(pack),
        "validation_errors": errors,
        "source_assets": source_receipt.get("attached_count", 0),
        "source_attachment": str(job_dir / "HOMS_SOURCE_ATTACHMENT_RECEIPT.json"),
        "paths": {
            "job_dir": str(job_dir),
            "assessment_pack": str(job_dir / "assessment_pack.json"),
            "formatted_review_docx": design_receipt["formatted_docx"],
            "learner_docx": str(learner_docx),
            "learner_pdf": str(learner_pdf) if learner_pdf else None,
            "review_pdf": str(review_pdf) if review_pdf else None,
            "zip": str(zip_path),
        },
    }
    write_json(job_dir / "HOMS_DETERMINISTIC_TERM_PACK_RECEIPT.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic CAPS-aware term packs for tight-8 Grade 12 subjects.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    started = time.perf_counter()
    args.out.mkdir(parents=True, exist_ok=True)
    receipts = []
    for subject_id in TIGHT8:
        for term in ["1", "2", "3", "4"]:
            print(json.dumps({"stage": "deterministic_pack_start", "subject": subject_id, "term": term}), flush=True)
            receipt = build_one(subject_id, term, args.out)
            receipts.append(receipt)
            print(json.dumps({"stage": "deterministic_pack_done", "subject": subject_id, "term": term, "status": receipt["status"]}), flush=True)
    manifest = {
        "schema": "knowedge.homs_tight8_deterministic_term_batch.v1",
        "created_at": utc_now(),
        "status": "passed" if all(r["status"] == "passed" for r in receipts) else "partial",
        "count": len(receipts),
        "passed": sum(1 for r in receipts if r["status"] == "passed"),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "receipts": receipts,
    }
    write_json(args.out / "HOMS_TIGHT8_DETERMINISTIC_TERM_BATCH.json", manifest)
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

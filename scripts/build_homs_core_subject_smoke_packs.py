#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apply_homs_design_law import DEFAULT_ASSESSMENT_DESIGN, DEFAULT_DESIGN_LAW, apply_design_law
from attach_homs_source_assets import DEFAULT_BANK, attach_sources


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "deliverables" / "homs_core_subject_smoke_packs"

CORE_PACKS = [
    {
        "subject_id": "physical_sciences",
        "subject": "Physical Sciences",
        "profile": "fet.physical_sciences",
        "family": "data_diagram_practical_investigation",
        "source_types": ["data_table", "diagram_or_model", "graph_or_chart"],
        "focus": "chemical and physical data, diagrams and graphs",
    },
    {
        "subject_id": "life_sciences",
        "subject": "Life Sciences",
        "profile": "fet.life_sciences",
        "family": "data_diagram_practical_investigation",
        "source_types": ["data_table", "diagram_or_model", "graph_or_chart"],
        "focus": "biological data, diagrams and evidence interpretation",
    },
    {
        "subject_id": "geography",
        "subject": "Geography",
        "profile": "fet.geography",
        "family": "source_based_plus_extended_response",
        "source_types": ["map_extract", "synoptic_weather_map", "graph_or_chart", "photograph_or_image"],
        "focus": "map, weather, graph and photograph source interpretation",
    },
    {
        "subject_id": "history",
        "subject": "History",
        "profile": "fet.history",
        "family": "source_based_plus_essay",
        "source_types": ["text_extract", "photograph_or_image", "cartoon", "data_table"],
        "focus": "historical source evidence, reliability and argument",
    },
    {
        "subject_id": "economics",
        "subject": "Economics",
        "profile": "fet.economics",
        "family": "case_study_structured_questions",
        "source_types": ["text_extract", "graph_or_chart", "data_table", "cartoon"],
        "focus": "economic case data, graphs, tables and cartoons",
    },
    {
        "subject_id": "mathematics",
        "subject": "Mathematics",
        "profile": "fet.mathematics",
        "family": "calculation_problem_solving",
        "source_types": ["diagram_or_model", "graph_or_chart", "data_table"],
        "focus": "graphs, diagrams and calculation evidence",
    },
    {
        "subject_id": "english_language",
        "subject": "English Language",
        "profile": "fet.english_language",
        "family": "language_integrated_assessment",
        "source_types": ["text_extract", "cartoon", "data_table", "photograph_or_image"],
        "focus": "language comprehension and visual literacy",
    },
    {
        "subject_id": "afrikaans_language",
        "subject": "Afrikaans",
        "profile": "fet.afrikaans_language",
        "family": "language_integrated_assessment",
        "source_types": ["text_extract", "cartoon", "graph_or_chart", "photograph_or_image"],
        "focus": "Afrikaans comprehension, literature context, visual literacy and writing prompts",
    },
    {
        "subject_id": "life_orientation",
        "subject": "Life Orientation",
        "profile": "fet.life_orientation",
        "family": "practical_performance_or_portfolio",
        "source_types": ["text_extract", "data_table"],
        "focus": "scenario, data and reflective response evidence for supervised CAT/portfolio tasks",
    },
]

ROUTE_ONLY_PACKS: list[dict[str, Any]] = []


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_") or "item"


def afrikaans_source_type(value: str) -> str:
    text = str(value or "").replace("_", " ").strip().lower()
    return {
        "text extract": "teksuittreksel",
        "cartoon": "spotprent",
        "graph or chart": "grafiek of diagram",
        "photograph or image": "foto of beeld",
        "data table": "datatabel",
        "diagram or model": "diagram of model",
        "map extract": "kaart-uittreksel",
        "synoptic weather map": "sinoptiese weerkaart",
    }.get(text, text)


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def base_pack(config: dict[str, Any]) -> dict[str, Any]:
    source_contract = config["source_types"]
    is_afrikaans = config["subject_id"] == "afrikaans_language"
    return {
        "schema": "knowedge.homs_assessment_pack.v1",
        "artifact_class": "internal_route_smoke",
        "release_gate": "blocked_internal_qa_not_a_learner_paper",
        "subject": config["subject"],
        "language_of_assessment": "Afrikaans" if is_afrikaans else "English",
        "grade": 12,
        "phase": "fet_grade_10_12",
        "assessment_title": (
            "INTERNE QA - Afrikaans Bronroete"
            if is_afrikaans
            else f"{config['subject']} Grade 12 Source-Embedded Smoke Test"
        ),
        "canonical_profile_id": config["profile"],
        "blueprint": config["family"],
        "total_marks": 30,
        "duration": "45 minute" if is_afrikaans else "45 minutes",
        "visual_blueprint": {
            "schema": "knowedge.homs_visual_blueprint.v1",
            "subject": config["subject"],
            "grade": 12,
            "phase": "fet_grade_10_12",
            "assessment_family": config["family"],
            "source_type_contract": {
                "schema": "knowedge.homs_source_type_contract.v1",
                "source_types": source_contract,
                "source_type_reasons": [
                    f"This smoke pack proves the {config['subject']} route can embed source material before question rendering.",
                    f"The subject focus is {config['focus']}.",
                    "Educator approval remains mandatory before classroom use.",
                ],
            },
            "required_visuals": [],
            "generation_constraints": [
                "Every source-referenced question must name a supplied SOURCE number.",
                "Questions must be answerable from visible source material and subject knowledge.",
                "Source readability, copyright/reuse status and CAPS fit must be reviewed by an educator.",
            ],
        },
        "sections": [
            {
                "title": "Broninterpretasie" if is_afrikaans else "Source Interpretation",
                "mode": "source_response",
                "instructions": (
                    "Gebruik die verskafde bronmateriaal. Beantwoord die vrae met sigbare bewyse en toepaslike vakkennis."
                    if is_afrikaans
                    else "Use the supplied source material. Answer from visible evidence and relevant subject knowledge."
                ),
                "questions": [],
            },
            {
                "title": "Metode En Kontrole" if is_afrikaans else "Method And Review",
                "mode": "review_response",
                "instructions": (
                    "Evalueer of hierdie gegenereerde assesseringspak gereed is vir 'n werklike leerdergroep."
                    if is_afrikaans
                    else "Evaluate whether this generated assessment pack is ready for a real learner group."
                ),
                "questions": [
                    {
                        "number": "2.1",
                        "question": (
                            "Noem TWEE kontroles wat 'n opvoeder moet uitvoer voordat hierdie assessering aan leerders gegee word."
                            if is_afrikaans
                            else "State TWO checks an educator must perform before releasing this assessment to learners."
                        ),
                        "marks": 4,
                        "memo": (
                            [
                                "Kontroleer bronleesbaarheid en relevansie.",
                                "Kontroleer CAPS-onderwerp- en graadbelyning.",
                                "Kontroleer puntetoekenning en memorandumkorrektheid.",
                                "Kontroleer kopiereg- en hergebruikvoorwaardes vir bronmateriaal.",
                            ]
                            if is_afrikaans
                            else [
                                "Check source readability and relevance.",
                                "Check CAPS topic/grade alignment.",
                                "Check mark allocation and memo correctness.",
                                "Check copyright/reuse conditions for source material.",
                            ]
                        ),
                    },
                    {
                        "number": "2.2",
                        "question": (
                            "Verduidelik waarom amptelike vraestel-bronvoorbeelde sterker is as generiese gegenereerde visuele materiaal vir hierdie roete."
                            if is_afrikaans
                            else "Explain why official-paper source exemplars are stronger than generic generated visuals for this route."
                        ),
                        "marks": 6,
                        "memo": (
                            [
                                "Dit wys werklike brontipes wat in vraestelle gebruik word.",
                                "Dit verminder uitgedinkte visuele nonsens.",
                                "Dit vereis steeds aanpassing en opvoedergoedkeuring.",
                            ]
                            if is_afrikaans
                            else [
                                "They reveal actual source types used in exams.",
                                "They reduce invented visual nonsense.",
                                "They still require adaptation and educator approval.",
                            ]
                        ),
                    },
                ],
            },
        ],
        "rubric": (
            [
                {"criterion": "Bronbewysgebruik", "marks": 10, "descriptor": "Antwoorde gebruik sigbare bewyse uit die verskafde bronne."},
                {"criterion": "Vakakkuraatheid", "marks": 10, "descriptor": "Antwoorde gebruik korrekte vakbegrippe en terminologie."},
                {"criterion": "Kontrolegereedheid", "marks": 10, "descriptor": "Risiko's en goedkeuringskontroles word duidelik geidentifiseer."},
            ]
            if is_afrikaans
            else [
                {"criterion": "Source evidence use", "marks": 10, "descriptor": "Answers use visible evidence from supplied sources."},
                {"criterion": "Subject accuracy", "marks": 10, "descriptor": "Answers use correct subject concepts and terminology."},
                {"criterion": "Review readiness", "marks": 10, "descriptor": "Risks and approval checks are identified clearly."},
            ]
        ),
        "teacher_review_checklist": (
            [
                "Bevestig dat elke ingebedde bron leesbaar is na PDF-uitvoer.",
                "Bevestig brongebruik en kopieregstatus voor klientlewering.",
                "Bevestig dat vrae slegs na verskafde of duidelik gestelde bewyse verwys.",
                "Bevestig dat memorandum en puntetoekenning by die vakroete pas.",
            ]
            if is_afrikaans
            else [
                "Confirm each embedded source is readable after PDF export.",
                "Confirm source use/copyright status before client delivery.",
                "Confirm questions refer only to supplied or clearly stated evidence.",
                "Confirm memo and mark allocation match the subject route.",
            ]
        ),
    }


def update_questions_for_sources(job_dir: Path) -> None:
    pack_path = job_dir / "assessment_pack.json"
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    is_afrikaans = (
        str(pack.get("language_of_assessment") or "").lower() == "afrikaans"
        or "afrikaans" in str(pack.get("subject") or "").lower()
    )
    source_assets = pack.get("source_assets") or []
    questions = []
    for index, asset in enumerate(source_assets, start=1):
        source_type = str(asset.get("source_type") or "source material").replace("_", " ")
        source_type_label = afrikaans_source_type(source_type) if is_afrikaans else source_type
        questions.append(
            {
                "number": f"1.{index}",
                "question": (
                    f"Verwys na BRON {index}. Identifiseer een belangrike kenmerk van die {source_type_label} en verduidelik hoe dit as bewys in Afrikaans gebruik kan word."
                    if is_afrikaans
                    else f"Refer to SOURCE {index}. Identify one important feature of the {source_type} and explain how it could be used as evidence in {pack['subject']}."
                ),
                "marks": 4,
                "memo": (
                    [
                        f"'n Relevante kenmerk uit BRON {index} word geidentifiseer.",
                        "Die verduideliking word aan die vakkonteks gekoppel.",
                        "Die antwoord gebruik sigbare bewyse eerder as onondersteunde onthouwerk.",
                    ]
                    if is_afrikaans
                    else [
                        f"Relevant feature from SOURCE {index} is identified.",
                        "Explanation is linked to the subject context.",
                        "Answer uses visible evidence rather than unsupported recall.",
                    ]
                ),
            }
        )
    questions.append(
        {
            "number": f"1.{len(questions) + 1}",
            "question": (
                "Vergelyk TWEE van die verskafde bronne. Verduidelik watter een die sterkste assesseringsvraag sou oplewer en waarom."
                if is_afrikaans
                else "Compare TWO of the supplied sources. Explain which one would produce the strongest assessment question and why."
            ),
            "marks": 5,
            "memo": (
                [
                    "Twee verskafde bronne word vergelyk.",
                    "'n Gemotiveerde oordeel word gemaak.",
                    "Redenering verwys na leesbaarheid, datarykheid, visuele duidelikheid of vakgeskiktheid.",
                ]
                if is_afrikaans
                else [
                    "Two supplied sources are compared.",
                    "A justified judgement is made.",
                    "Reasoning mentions readability, data richness, visual clarity or subject fit.",
                ]
            ),
        }
    )
    pack["sections"][0]["questions"] = questions
    pack["total_marks"] = sum(int(q.get("marks") or 0) for section in pack["sections"] for q in section.get("questions", []))
    write_json(pack_path, pack)


def build_pack(config: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    job_dir = out_dir / f"{config['subject_id']}_g12_source_smoke"
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "LEARNER_RELEASE_BLOCKED.txt").write_text(
        "INTERNAL ROUTE QA ONLY. This folder is not a learner assessment and must not be delivered as one.\n",
        encoding="utf-8",
    )
    write_json(job_dir / "assessment_pack.json", base_pack(config))
    attachment = attach_sources(
        job_dir=job_dir,
        bank_path=DEFAULT_BANK.resolve(),
        explicit_subject=config["subject_id"],
        explicit_types=",".join(config["source_types"]),
        limit=len(config["source_types"]),
        dry_run=False,
    )
    update_questions_for_sources(job_dir)
    render_receipt = apply_design_law(job_dir, DEFAULT_DESIGN_LAW, DEFAULT_ASSESSMENT_DESIGN)
    return {
        "subject_id": config["subject_id"],
        "subject": config["subject"],
        "job_dir": str(job_dir),
        "status": "formatted",
        "requested_source_types": attachment["requested_source_types"],
        "attached_count": attachment["attached_count"],
        "missing_requested_source_types": attachment.get("missing_requested_source_types") or [],
        "formatted_docx": render_receipt["formatted_docx"],
        "formatted_zip": render_receipt["formatted_zip"],
        "visual_manifest": render_receipt["visual_manifest"],
    }


def write_summary(out_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# HOMS Core Subject Smoke Packs",
        "",
        "Purpose: prove that the high-demand FET subject routes can attach source-bank assets, render source material in DOCX, and produce a review zip.",
        "",
        f"- Created at: {payload['created_at']}",
        f"- Built packs: {len(payload['built'])}",
        f"- Route-only subjects: {len(payload['route_only'])}",
        "",
        "## Built Packs",
        "",
        "| Subject | Sources | Missing Source Types | Output |",
        "|---|---:|---|---|",
    ]
    for item in payload["built"]:
        missing = ", ".join(f"`{source}`" for source in item["missing_requested_source_types"]) or "none"
        lines.append(f"| {item['subject']} | {item['attached_count']} | {missing} | `{Path(item['formatted_docx']).relative_to(ROOT)}` |")
    lines.extend(["", "## Route-Only", "", "| Subject | Reason |", "|---|---|"])
    for item in payload["route_only"]:
        lines.append(f"| {item['subject']} | {item['reason']} |")
    lines.extend(
        [
            "",
            "## Operating Note",
            "",
            "These are smoke packs, not final classroom papers. A smoke pack passing means the route can embed and audit source material. Final product quality still depends on subject-specific question generation, source cropping/readability and educator approval.",
        ]
    )
    (out_dir / "HOMS_CORE_SUBJECT_SMOKE_SUMMARY.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    out_dir = DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    built = [build_pack(config, out_dir) for config in CORE_PACKS]
    payload = {
        "schema": "knowedge.homs_core_subject_smoke_packs.v1",
        "created_at": utc_now(),
        "built": built,
        "route_only": ROUTE_ONLY_PACKS,
    }
    write_json(out_dir / "HOMS_CORE_SUBJECT_SMOKE_SUMMARY.json", payload)
    write_summary(out_dir, payload)
    print(json.dumps({"status": "completed", "out_dir": str(out_dir), "built": len(built), "route_only": len(ROUTE_ONLY_PACKS)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

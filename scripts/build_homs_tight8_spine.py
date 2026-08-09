#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "deliverables" / "homs_tight8_spine"
SMOKE_VALIDATION = ROOT / "deliverables" / "homs_core_subject_smoke_packs" / "HOMS_CORE_SUBJECT_SMOKE_VALIDATION.json"
CURATED_BANK = ROOT / "deliverables" / "homs_core_source_bank_curated" / "HOMS_CORE_SOURCE_BANK_CURATED.json"


TIGHT8 = [
    {
        "subject_id": "english_language",
        "display_name": "English Language",
        "fet_anchor": "English Home Language / English First Additional Language",
        "source_grammar": ["text_extract", "cartoon", "photograph_or_image", "data_table"],
        "phase_translation": {
            "fet_10_12": "language_integrated_assessment: comprehension, visual literacy, summary, transactional/creative writing",
            "senior_7_9": "language_integrated_assessment: source reading, language-in-context, paragraph response",
            "intermediate_4_6": "guided_language_task: text comprehension, vocabulary, simple visual interpretation",
            "foundation_1_3": "early_language_task: oral prompt, picture prompt, phonics/vocabulary, sentence response",
        },
        "caps_bridge": [
            "corpora/caps/pdf/fet_grade_10_12/caps_fet_home_english_gr_10-12_web_5478.pdf",
            "corpora/caps/pdf/intermediate_grade_4_6/caps_ip_home_english_gr_4-6_web.pdf",
            "corpora/caps/pdf/foundation_grade_r_3/caps_english_hl_grades_r-3_fs.pdf",
        ],
        "done_definition": [
            "official/curricular text and visual source candidates are embedded",
            "language shell handles comprehension, visual literacy and writing tasks separately",
            "reading and writing load obeys grade ladder",
        ],
    },
    {
        "subject_id": "afrikaans_language",
        "display_name": "Afrikaans Language",
        "fet_anchor": "Afrikaans Home Language / Afrikaans First Additional Language",
        "source_grammar": ["text_extract", "cartoon", "photograph_or_image", "data_table"],
        "phase_translation": {
            "fet_10_12": "language_integrated_assessment: comprehension, visual literacy, summary, writing",
            "senior_7_9": "language_integrated_assessment: source reading, taal-in-konteks, paragraph response",
            "intermediate_4_6": "guided_language_task: reading, vocabulary, sentence/paragraph scaffold",
            "foundation_1_3": "early_language_task: oral/picture prompts, vocabulary, sentence response",
        },
        "caps_bridge": [
            "corpora/caps/pdf/fet_grade_10_12/caps_fet_home_afrikaans_gr_10-12_web_0544.pdf",
            "corpora/caps/pdf/fet_grade_10_12/caps_fet_fal_afrikaans_gr_10-12_web_9455.pdf",
            "corpora/caps/pdf/intermediate_grade_4_6/caps_ip_home_afrikaans_gr_4-6_web.pdf",
            "corpora/caps/pdf/foundation_grade_r_3/caps_afrikaans_home_language_gr_r-3_fs.pdf",
        ],
        "done_definition": [
            "Afrikaans source exemplars are added to the source bank",
            "language shell supports Afrikaans instructions and memo wording",
            "HL/FAL/SAL level is explicit in the request and receipt",
        ],
    },
    {
        "subject_id": "mathematics",
        "display_name": "Mathematics",
        "fet_anchor": "Mathematics",
        "source_grammar": ["diagram_or_model", "graph_or_chart", "data_table", "number_line_or_grid"],
        "phase_translation": {
            "fet_10_12": "calculation_problem_solving: graph, geometry, algebra, data handling",
            "senior_7_9": "pre_fet_problem_solving: multi-step calculations, graphs, geometry and pattern reasoning",
            "intermediate_4_6": "guided_problem_solving: number operations, tables, simple graphs, measurement",
            "foundation_1_3": "concrete_number_task: number line, counting objects, shapes, measurement pictures",
        },
        "caps_bridge": [
            "corpora/caps/pdf/fet_grade_10_12/caps_fet_mathematics_gr_10-12_web_1133.pdf",
            "corpora/caps/pdf/senior_grade_7_9/caps_sp_mathematics_gr_7-9.pdf",
            "corpora/caps/pdf/intermediate_grade_4_6/caps_ip_mathematics_gr_4-6_web.pdf",
            "corpora/caps/pdf/foundation_grade_r_3/caps_maths_english_gr_1-3_fs.pdf",
        ],
        "done_definition": [
            "graph/diagram/table source candidates are readable",
            "answers are mechanically derivable from supplied values",
            "memo separates method, substitution, final answer and unit marks",
        ],
    },
    {
        "subject_id": "life_orientation",
        "display_name": "Life Orientation / Life Skills",
        "fet_anchor": "Life Orientation",
        "source_grammar": ["scenario", "case_extract", "reflection_prompt", "rubric_checklist"],
        "phase_translation": {
            "fet_10_12": "practical_performance_or_portfolio: scenario, reflection, project and rubric evidence",
            "senior_7_9": "life_orientation_task: scenario response, decision-making, wellbeing/citizenship evidence",
            "intermediate_4_6": "life_skills_task: personal/social wellbeing, creative arts/physical education evidence",
            "foundation_1_3": "life_skills_activity: oral/picture prompt, observation checklist, concrete wellbeing/environment tasks",
        },
        "caps_bridge": [
            "corpora/caps/pdf/fet_grade_10_12/caps_fet_life_orientation_gr_10-12_web_e6b3.pdf",
            "corpora/caps/pdf/senior_grade_7_9/caps_sp_life_orientation_web.pdf",
            "corpora/caps/pdf/intermediate_grade_4_6/caps_ip_life_skills_gr_4-6_web.pdf",
            "corpora/caps/pdf/foundation_grade_r_3/caps_life_skills_english_gr_r-3_fs.pdf",
        ],
        "done_definition": [
            "assessment avoids unsafe/private/sensitive prompts",
            "portfolio/performance evidence is separated from written reflection",
            "educator observation rubric is always included",
        ],
    },
    {
        "subject_id": "life_sciences",
        "display_name": "Life Sciences -> Natural Sciences Life Strand",
        "fet_anchor": "Life Sciences",
        "source_grammar": ["data_table", "diagram_or_model", "graph_or_chart", "investigation_sheet"],
        "phase_translation": {
            "fet_10_12": "data_diagram_practical_investigation: biological data, diagrams, investigation reasoning",
            "senior_7_9": "natural_sciences_life_living: diagrams, practical observations, data interpretation",
            "intermediate_4_6": "natural_sciences_technology_life_living: labelled diagrams, simple tables, observation sheets",
            "foundation_1_3": "life_skills_beginning_knowledge: living/non-living, body/environment picture prompts",
        },
        "caps_bridge": [
            "corpora/caps/pdf/fet_grade_10_12/caps_fet_life_sciences_gr_10-12_web_2636.pdf",
            "corpora/caps/pdf/senior_grade_7_9/caps_sp_natural_sciences_gr_7-9_web.pdf",
            "corpora/caps/pdf/intermediate_grade_4_6/caps_ip_natural_sciences_technology_web.pdf",
            "corpora/caps/pdf/foundation_grade_r_3/caps_life_skills_english_gr_r-3_fs.pdf",
        ],
        "done_definition": [
            "biology diagrams are source-verified or explicitly schematic",
            "Life Sciences graph exemplar gap is closed",
            "human/anatomy diagrams are blocked until educator/source review",
        ],
    },
    {
        "subject_id": "physical_sciences",
        "display_name": "Physical Sciences -> Natural Sciences Physical Strand",
        "fet_anchor": "Physical Sciences",
        "source_grammar": ["data_table", "diagram_or_model", "graph_or_chart", "calculation_values"],
        "phase_translation": {
            "fet_10_12": "data_diagram_practical_investigation: apparatus, graphs, calculations, equations",
            "senior_7_9": "natural_sciences_matter_energy_planet: experiments, graphs, diagrams, explanations",
            "intermediate_4_6": "natural_sciences_technology_matter_energy: simple investigations, tables, labelled diagrams",
            "foundation_1_3": "life_skills_beginning_knowledge: materials, weather, movement, simple observation tasks",
        },
        "caps_bridge": [
            "corpora/caps/pdf/fet_grade_10_12/caps_fet_physical_science_web.pdf",
            "corpora/caps/pdf/senior_grade_7_9/caps_sp_natural_sciences_gr_7-9_web.pdf",
            "corpora/caps/pdf/intermediate_grade_4_6/caps_ip_natural_sciences_technology_web.pdf",
            "corpora/caps/pdf/foundation_grade_r_3/caps_life_skills_english_gr_r-3_fs.pdf",
        ],
        "done_definition": [
            "source graph/diagram/table candidates are readable",
            "all calculation questions include values and units",
            "unsafe practical instructions are blocked",
        ],
    },
    {
        "subject_id": "geography",
        "display_name": "Geography -> Social Sciences Geography",
        "fet_anchor": "Geography",
        "source_grammar": ["map_extract", "synoptic_weather_map", "photograph_or_image", "graph_or_chart", "data_table"],
        "phase_translation": {
            "fet_10_12": "source_based_plus_extended_response: maps, climate, geomorphology, settlement/economic sources",
            "senior_7_9": "social_sciences_geography: maps, climate, population, settlement, resource sources",
            "intermediate_4_6": "social_sciences_geography: simple maps, photographs, diagrams, tables",
            "foundation_1_3": "life_skills_beginning_knowledge: places, weather, environment, simple map/picture awareness",
        },
        "caps_bridge": [
            "corpora/caps/pdf/fet_grade_10_12/caps_fet_geography_gr_10-12_web_c9a9.pdf",
            "corpora/caps/pdf/intermediate_grade_4_6/caps_ip_social_sciences_web.pdf",
            "corpora/caps/pdf/foundation_grade_r_3/caps_life_skills_english_gr_r-3_fs.pdf",
        ],
        "done_definition": [
            "maps and photos are object-level curated, not page dumps",
            "source classifier mismatches are resolved before release",
            "questions never ask learners to answer from a missing map/visual",
        ],
    },
    {
        "subject_id": "history",
        "display_name": "History -> Social Sciences History",
        "fet_anchor": "History",
        "source_grammar": ["text_extract", "photograph_or_image", "cartoon", "data_table"],
        "phase_translation": {
            "fet_10_12": "source_based_plus_essay: source reliability, evidence comparison, essay argument",
            "senior_7_9": "social_sciences_history: source evidence, cause/effect, paragraph explanation",
            "intermediate_4_6": "social_sciences_history: stories, timelines, pictures, simple source questions",
            "foundation_1_3": "life_skills_beginning_knowledge: past/present, family/community stories, sequencing",
        },
        "caps_bridge": [
            "corpora/caps/pdf/fet_grade_10_12/caps_fet_history_gr_10-12_web_1.pdf",
            "corpora/caps/pdf/fet_grade_10_12/caps_fet_afrikaans_geskiedenis_gr_10-12_web.pdf",
            "corpora/caps/pdf/intermediate_grade_4_6/caps_ip_social_sciences_web.pdf",
            "corpora/caps/pdf/foundation_grade_r_3/caps_life_skills_english_gr_r-3_fs.pdf",
        ],
        "done_definition": [
            "each source set has provenance and visible evidence",
            "essay/paragraph length is phase appropriate",
            "memo accepts defensible evidence-linked answers",
        ],
    },
]

EXTENSIONS = [
    {
        "subject_id": "economics",
        "display_name": "Economics / EMS Extension",
        "reason_not_spine": "valuable FET product, but it maps directly to Senior Phase EMS and only indirectly to Foundation/Intermediate money and community themes",
        "carry_down": {
            "fet_10_12": "Economics",
            "senior_7_9": "Economic and Management Sciences",
            "intermediate_4_6": "Mathematics money/data and Social Sciences community/economy themes",
            "foundation_1_3": "Life Skills/Mathematics money, needs/wants and community helper concepts",
        },
    }
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def file_exists(path: str) -> bool:
    return (ROOT / path).exists()


def subject_validation() -> dict[str, dict[str, Any]]:
    validation = load_json(SMOKE_VALIDATION)
    return {item["subject_id"]: item for item in validation.get("results") or []}


def curated_bank_by_subject() -> dict[str, list[dict[str, Any]]]:
    bank = load_json(CURATED_BANK)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for asset in bank.get("assets") or []:
        grouped.setdefault(asset["subject_id"], []).append(asset)
    return grouped


def spine_payload() -> dict[str, Any]:
    validation = subject_validation()
    bank = curated_bank_by_subject()
    subjects = []
    for row in TIGHT8:
        assets = bank.get(row["subject_id"], [])
        validation_row = validation.get(row["subject_id"], {})
        caps_missing = [path for path in row["caps_bridge"] if not file_exists(path)]
        release_blocked = int(validation_row.get("release_blocked_sources") or 0)
        source_assets = len(assets)
        if caps_missing:
            status = "blocked_missing_caps_bridge"
        elif not source_assets:
            status = "route_ready_source_bank_missing"
        elif validation_row.get("status") == "passed" and release_blocked:
            status = "mechanics_passed_release_blocked"
        elif validation_row.get("status") == "passed":
            status = "candidate_ready_for_human_review"
        else:
            status = "needs_smoke_pack"
        subjects.append(
            {
                **row,
                "status": status,
                "source_bank_assets": source_assets,
                "smoke_status": validation_row.get("status"),
                "release_blocked_sources": release_blocked,
                "missing_requested_source_types": validation_row.get("missing_requested_source_types") or [],
                "caps_missing": caps_missing,
            }
        )
    return {
        "schema": "knowedge.homs_tight8_spine.v1",
        "created_at": utc_now(),
        "definition": "The tight 8 are the school-subject spine lanes that can be translated downward from FET to Senior, Intermediate and Foundation phases.",
        "subjects": subjects,
        "extensions": EXTENSIONS,
        "release_rule": "No subject is sellable until source release gates are cleared and educator approval is recorded.",
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# HOMS Tight 8 Spine",
        "",
        payload["definition"],
        "",
        "Economics is tracked as an extension lane, not part of the tight 8 spine, because it does not carry down to Grade 3 as directly as languages, mathematics, life skills, natural sciences and social sciences.",
        "",
        "## Status",
        "",
        "| Spine | Status | Source Assets | Release Blocked | Missing Source Types | Downward Carrier |",
        "|---|---|---:|---:|---|---|",
    ]
    for item in payload["subjects"]:
        missing = ", ".join(f"`{source}`" for source in item["missing_requested_source_types"]) or "none"
        carrier = item["phase_translation"]["foundation_1_3"]
        lines.append(
            f"| {item['display_name']} | `{item['status']}` | {item['source_bank_assets']} | {item['release_blocked_sources']} | {missing} | {carrier} |"
        )
    lines.extend(["", "## Phase Translation", ""])
    for item in payload["subjects"]:
        lines.append(f"### {item['display_name']}")
        lines.append("")
        for phase, value in item["phase_translation"].items():
            lines.append(f"- `{phase}`: {value}")
        lines.append("- Done means: " + "; ".join(item["done_definition"]))
        if item["caps_missing"]:
            lines.append("- Missing CAPS files: " + ", ".join(f"`{path}`" for path in item["caps_missing"]))
        lines.append("")
    lines.extend(["## Extension Lane", ""])
    for item in payload["extensions"]:
        lines.append(f"- {item['display_name']}: {item['reason_not_spine']}")
    lines.extend(["", "## Release Rule", "", payload["release_rule"]])
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    out_dir = DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = spine_payload()
    (out_dir / "HOMS_TIGHT8_SPINE.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_markdown(out_dir / "HOMS_TIGHT8_SPINE.md", payload)
    status_counts: dict[str, int] = {}
    for subject in payload["subjects"]:
        status_counts[subject["status"]] = status_counts.get(subject["status"], 0) + 1
    print(json.dumps({"status": "completed", "out_dir": str(out_dir), "subjects": len(payload["subjects"]), "status_counts": status_counts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

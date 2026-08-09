#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_homs_nim_contextual_assessment import (  # noqa: E402
    DEFAULT_CAPS_ASSESSMENT_DESIGN,
    DEFAULT_CAPS_MANIFEST,
    DEFAULT_CAPS_MATRIX,
    DEFAULT_CAPS_ONTOLOGY,
    DEFAULT_DESIGN_LAW,
    DEFAULT_GRADE_LADDER,
    DEFAULT_HYMARK_BACKEND,
    DEFAULT_KNOWLEDGE_BANK,
    DEFAULT_SECRET_FILE,
    DEFAULT_SOURCE_MATRIX,
    run as run_contextual_pack,
)


DEFAULT_OUT = ROOT / "deliverables" / "homs_tight8_term_contextual_packs"

TIGHT8 = [
    "english_language",
    "afrikaans_language",
    "life_orientation",
    "mathematics",
    "physical_sciences",
    "life_sciences",
    "geography",
    "history",
]

TERM_FOCI: dict[str, dict[str, dict[str, str]]] = {
    "english_language": {
        "1": {
            "focus": "comprehension, language in context and visual literacy",
            "secondary_focus": "tone, audience, purpose, inference and evidence from a supplied text",
            "methodology_focus": "summary planning and precise language editing",
            "extended_focus": "transactional writing with register, structure and audience control",
        },
        "2": {
            "focus": "literary extract, character, theme and language analysis",
            "secondary_focus": "visual literacy and media message interpretation",
            "methodology_focus": "quote selection, evidence integration and paragraph structure",
            "extended_focus": "discursive or argumentative writing with coherent development",
        },
        "3": {
            "focus": "integrated comprehension, summary and language structures",
            "secondary_focus": "cartoon, advertisement or infographic analysis",
            "methodology_focus": "editing for grammar, diction, register and punctuation",
            "extended_focus": "formal transactional writing and controlled response planning",
        },
        "4": {
            "focus": "final integrated language examination practice",
            "secondary_focus": "unseen text interpretation and visual literacy synthesis",
            "methodology_focus": "time-managed summary, editing and evidence-based answers",
            "extended_focus": "extended writing with argument, coherence and style control",
        },
    },
    "afrikaans_language": {
        "1": {
            "focus": "begripstoets, taal in konteks en visuele geletterdheid",
            "secondary_focus": "toon, teikengroep, doel, afleiding en bewyse uit 'n gegewe teks",
            "methodology_focus": "opsommingsbeplanning en noukeurige taalredigering",
            "extended_focus": "transaksionele skryfwerk met register, struktuur en teikengroepbeheer",
        },
        "2": {
            "focus": "literere uittreksel, karakter, tema en taalontleding",
            "secondary_focus": "visuele geletterdheid en media-boodskapinterpretasie",
            "methodology_focus": "aanhalingskeuse, bewysinvoeging en paragraafstruktuur",
            "extended_focus": "beredenerende of argumenterende skryfwerk met samehangende ontwikkeling",
        },
        "3": {
            "focus": "geintegreerde begrip, opsomming en taalstrukture",
            "secondary_focus": "spotprent-, advertensie- of infografika-ontleding",
            "methodology_focus": "redigering vir grammatika, woordkeuse, register en leestekens",
            "extended_focus": "formele transaksionele skryfwerk en beheerde antwoordbeplanning",
        },
        "4": {
            "focus": "finale geintegreerde taaleksamenoefening",
            "secondary_focus": "onvoorbereide teksinterpretasie en visuele geletterdheidsintese",
            "methodology_focus": "tydbestuurde opsomming, redigering en bewysgebaseerde antwoorde",
            "extended_focus": "uitgebreide skryfwerk met argument, samehang en stylbeheer",
        },
    },
    "life_orientation": {
        "1": {
            "focus": "development of the self in society and goal-directed choices",
            "secondary_focus": "wellbeing, relationships, stress management and responsible decision-making",
            "methodology_focus": "scenario evidence, reflective response and support strategy evaluation",
            "extended_focus": "personal action plan with safe, non-invasive educator review",
        },
        "2": {
            "focus": "social and environmental responsibility",
            "secondary_focus": "rights, responsibilities, community participation and media influence",
            "methodology_focus": "case-study decision-making and evidence-based recommendation",
            "extended_focus": "portfolio or project response with rubric-marked reflection",
        },
        "3": {
            "focus": "careers, study pathways and workplace readiness",
            "secondary_focus": "career data, subject choices, employability and post-school options",
            "methodology_focus": "interpreting pathway information and justifying choices",
            "extended_focus": "practical plan for study, work exposure or career investigation",
        },
        "4": {
            "focus": "integrated Life Orientation CAT and portfolio consolidation",
            "secondary_focus": "democracy, health, physical education and civic responsibility",
            "methodology_focus": "scenario analysis, reflection and supervised evidence collation",
            "extended_focus": "final reflective task with educator-marked rubric evidence",
        },
    },
    "mathematics": {
        "1": {
            "focus": "functions, algebra, equations and financial mathematics",
            "secondary_focus": "graphs, transformations, inverses and interpretation of parameters",
            "methodology_focus": "showing algebraic working and linking graphs to equations",
            "extended_focus": "multi-step problem solving with method marks and final answer checks",
        },
        "2": {
            "focus": "calculus, rates of change, analytical geometry and trigonometry",
            "secondary_focus": "derivatives, tangents, optimisation and coordinate reasoning",
            "methodology_focus": "formula selection, substitution, proof steps and unit control",
            "extended_focus": "integrated calculation problem with graph or diagram interpretation",
        },
        "3": {
            "focus": "statistics, probability, Euclidean geometry and measurement",
            "secondary_focus": "data displays, probability rules and geometric proof",
            "methodology_focus": "interpreting diagrams, justifying steps and checking constraints",
            "extended_focus": "mixed-topic source-based calculation paper",
        },
        "4": {
            "focus": "final integrated Mathematics examination practice",
            "secondary_focus": "functions, calculus, geometry, trigonometry, statistics and probability",
            "methodology_focus": "time-managed worked solutions with method and accuracy marks",
            "extended_focus": "cross-topic problem solving and proof readiness",
        },
    },
    "physical_sciences": {
        "1": {
            "focus": "mechanics, momentum, vertical projectile motion and Newton's laws",
            "secondary_focus": "force diagrams, motion graphs, impulse and conservation of momentum",
            "methodology_focus": "formula selection, substitution, units and sign convention",
            "extended_focus": "investigation or data-response task using motion evidence",
        },
        "2": {
            "focus": "electric circuits, electrodynamics and waves",
            "secondary_focus": "Ohm's law, power, internal resistance, generators and motors",
            "methodology_focus": "circuit interpretation, graph reading and calculation working",
            "extended_focus": "apparatus/data task with controlled variables and conclusion",
        },
        "3": {
            "focus": "chemical change, equilibrium, acids and bases, electrochemical cells",
            "secondary_focus": "reaction rates, Le Chatelier, pH, titration and redox reasoning",
            "methodology_focus": "balanced equations, calculations, data interpretation and method critique",
            "extended_focus": "practical investigation pack with graph/table evidence",
        },
        "4": {
            "focus": "final integrated Physical Sciences examination practice",
            "secondary_focus": "mechanics, electricity, chemical change and organic chemistry",
            "methodology_focus": "mixed calculations, graph interpretation and experimental design",
            "extended_focus": "source-linked final revision paper with memo-ready mark allocation",
        },
    },
    "life_sciences": {
        "1": {
            "focus": "DNA, meiosis, genetics and inheritance patterns",
            "secondary_focus": "protein synthesis, mutations, pedigrees and genetic variation",
            "methodology_focus": "interpreting genetic crosses, diagrams and data tables",
            "extended_focus": "application of inheritance evidence to explain biological variation",
        },
        "2": {
            "focus": "reproduction, homeostasis and response to the environment",
            "secondary_focus": "human endocrine control, nervous coordination and reproductive strategies",
            "methodology_focus": "diagram interpretation, feedback loops and investigation design",
            "extended_focus": "data-based explanation of biological regulation and reproduction",
        },
        "3": {
            "focus": "Evolution by natural selection and speciation",
            "secondary_focus": "Human evolution evidence and interpretation",
            "methodology_focus": "Scientific investigation design for natural selection",
            "extended_focus": "Using data and anatomical evidence to support evolutionary explanations",
        },
        "4": {
            "focus": "final integrated Life Sciences examination practice",
            "secondary_focus": "genetics, evolution, reproduction, homeostasis and investigation skills",
            "methodology_focus": "data, diagrams, variables, validity, reliability and conclusion writing",
            "extended_focus": "cross-topic biological reasoning with source and diagram evidence",
        },
    },
    "geography": {
        "1": {
            "focus": "climate, weather systems and geomorphology",
            "secondary_focus": "synoptic weather maps, drainage basins, fluvial processes and slopes",
            "methodology_focus": "map, diagram, graph and data interpretation",
            "extended_focus": "process explanation supported by spatial and numeric evidence",
        },
        "2": {
            "focus": "rural and urban settlement geography",
            "secondary_focus": "settlement patterns, land use, urban problems and sustainability",
            "methodology_focus": "interpreting maps, photographs, data tables and case evidence",
            "extended_focus": "structured extended response on human-environment interaction",
        },
        "3": {
            "focus": "economic geography, development and GIS/mapwork",
            "secondary_focus": "industry, trade, transport, spatial inequality and geographic data",
            "methodology_focus": "map scale, coordinates, graphs, tables and spatial reasoning",
            "extended_focus": "source-based economic geography response with map/data support",
        },
        "4": {
            "focus": "final integrated Geography examination practice",
            "secondary_focus": "climate, geomorphology, settlement, economic geography, GIS and mapwork",
            "methodology_focus": "source interpretation across maps, photographs, diagrams and data",
            "extended_focus": "extended geographical argument using spatial evidence",
        },
    },
    "history": {
        "1": {
            "focus": "Cold War, Cuban Missile Crisis and the division of Germany",
            "secondary_focus": "source reliability, perspective, causation and consequence",
            "methodology_focus": "provenance, contextualisation and evidence comparison",
            "extended_focus": "argumentative essay using historical evidence and chronology",
        },
        "2": {
            "focus": "independent Africa and comparative case studies",
            "secondary_focus": "leadership, ideology, state-building and economic challenges",
            "methodology_focus": "source comparison, usefulness and historical interpretation",
            "extended_focus": "essay on change, continuity and post-colonial development",
        },
        "3": {
            "focus": "civil society protest, civil rights, Black Power and resistance to apartheid",
            "secondary_focus": "oral testimony, speeches, photographs and political cartoons",
            "methodology_focus": "bias, reliability, limitation and corroboration",
            "extended_focus": "evidence-based essay on resistance movements and impact",
        },
        "4": {
            "focus": "final integrated History source-based and essay examination practice",
            "secondary_focus": "Cold War, independent Africa, civil rights and apartheid resistance",
            "methodology_focus": "source set analysis, provenance, usefulness, reliability and argument",
            "extended_focus": "timed essay with claim, evidence and judgement",
        },
    },
}

DEFAULT_MARKS = {
    "english_language": 70,
    "afrikaans_language": 70,
    "life_orientation": 50,
}

DEFAULT_DURATION = {
    "english_language": "2 hours",
    "afrikaans_language": "2 uur",
    "life_orientation": "1 hour",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_csv(value: str, allowed: list[str]) -> list[str]:
    if value.strip().lower() in {"all", "tight8"}:
        return allowed
    requested = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [item for item in requested if item not in allowed]
    if unknown:
        raise ValueError(f"Unknown values: {', '.join(unknown)}")
    return requested


def args_for_pack(args: argparse.Namespace, subject: str, term: str) -> argparse.Namespace:
    focus = TERM_FOCI[subject][term]
    total_marks = int(args.total_marks or DEFAULT_MARKS.get(subject, 75))
    duration = args.duration or DEFAULT_DURATION.get(subject, "1.5 hours")
    return argparse.Namespace(
        subject=subject,
        grade=args.grade,
        term=term,
        focus=focus["focus"],
        secondary_focus=focus["secondary_focus"],
        methodology_focus=focus["methodology_focus"],
        extended_focus=focus["extended_focus"],
        total_marks=total_marks,
        duration=duration,
        duration_hours=args.duration_hours,
        opportunity=f"Term {term} controlled assessment",
        request=None,
        out=args.out,
        provider=args.provider,
        model=args.model,
        secret_file=args.secret_file,
        backend=args.backend,
        grade_ladder=args.grade_ladder,
        caps_manifest=args.caps_manifest,
        caps_matrix=args.caps_matrix,
        caps_ontology=args.caps_ontology,
        caps_assessment_design=args.caps_assessment_design,
        design_law=args.design_law,
        source_matrix=args.source_matrix,
        knowledge_bank=args.knowledge_bank,
        preferred_language="Afrikaans" if subject == "afrikaans_language" else args.preferred_language,
        caps_extract_chars=args.caps_extract_chars,
        repair=args.repair,
        timeout=args.timeout,
        max_tokens=args.max_tokens,
    )


def existing_passed_receipt(out_dir: Path, subject: str, term: str) -> dict[str, Any] | None:
    if not out_dir.exists():
        return None
    for receipt_path in sorted(out_dir.glob(f"*-context-{subject}-g*-t{term}-*/HOMS_CONTEXTUAL_ASSESSMENT_RECEIPT.json"), reverse=True):
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if receipt.get("status") == "passed":
            return receipt
    return None


def run_batch(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    subjects = parse_csv(args.subjects, TIGHT8)
    terms = parse_csv(args.terms, ["1", "2", "3", "4"])
    args.out.mkdir(parents=True, exist_ok=True)
    receipts: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    planned = [(subject, term) for subject in subjects for term in terms]
    if args.limit:
        planned = planned[: args.limit]
    for index, (subject, term) in enumerate(planned, start=1):
        if args.resume:
            existing = existing_passed_receipt(args.out, subject, term)
            if existing:
                receipts.append(existing)
                print(
                    json.dumps(
                        {
                            "stage": "tight8_pack_skipped_existing_passed",
                            "index": index,
                            "total": len(planned),
                            "subject": subject,
                            "term": term,
                            "job_dir": (existing.get("paths") or {}).get("job_dir"),
                        }
                    ),
                    flush=True,
                )
                continue
        print(json.dumps({"stage": "tight8_pack_start", "index": index, "total": len(planned), "subject": subject, "term": term}), flush=True)
        try:
            receipt = run_contextual_pack(args_for_pack(args, subject, term))
            receipts.append(receipt)
            print(
                json.dumps(
                    {
                        "stage": "tight8_pack_done",
                        "subject": subject,
                        "term": term,
                        "status": receipt.get("status"),
                        "job_dir": (receipt.get("paths") or {}).get("job_dir"),
                    }
                ),
                flush=True,
            )
        except Exception as exc:
            failure = {
                "subject": subject,
                "term": term,
                "error_type": type(exc).__name__,
                "error": str(exc)[:500],
            }
            failures.append(failure)
            print(json.dumps({"stage": "tight8_pack_failed", **failure}), flush=True)
            if not args.continue_on_fail:
                break
        if args.sleep_between > 0 and index < len(planned):
            time.sleep(args.sleep_between)
    passed = [item for item in receipts if item.get("status") == "passed"]
    failed_validation = [item for item in receipts if item.get("status") != "passed"]
    manifest = {
        "schema": "knowedge.homs_tight8_term_contextual_batch.v1",
        "created_at": utc_now(),
        "status": "passed" if len(passed) == len(planned) and not failures else "partial",
        "provider": args.provider,
        "model": args.model or None,
        "grade": args.grade,
        "subjects": subjects,
        "terms": terms,
        "planned_count": len(planned),
        "completed_count": len(receipts),
        "passed_count": len(passed),
        "failed_validation_count": len(failed_validation),
        "exception_count": len(failures),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "receipts": receipts,
        "failures": failures,
    }
    write_json(args.out / "HOMS_TIGHT8_TERM_CONTEXTUAL_BATCH.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build provider-backed contextual HOMS packs for each term across the tight 8 FET subjects.")
    parser.add_argument("--subjects", default="tight8", help="Comma-separated subject IDs or tight8/all.")
    parser.add_argument("--terms", default="1,2,3,4", help="Comma-separated terms from 1,2,3,4.")
    parser.add_argument("--grade", type=int, default=12)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--provider", default="gemini", choices=["gemini", "google", "openrouter", "deepseek", "deepseek_v4", "nim", "nvidia", "nvidia_nim", "openai"])
    parser.add_argument("--model", default="")
    parser.add_argument("--secret-file", type=Path, default=DEFAULT_SECRET_FILE)
    parser.add_argument("--backend", type=Path, default=DEFAULT_HYMARK_BACKEND)
    parser.add_argument("--grade-ladder", type=Path, default=DEFAULT_GRADE_LADDER)
    parser.add_argument("--caps-manifest", type=Path, default=DEFAULT_CAPS_MANIFEST)
    parser.add_argument("--caps-matrix", type=Path, default=DEFAULT_CAPS_MATRIX)
    parser.add_argument("--caps-ontology", type=Path, default=DEFAULT_CAPS_ONTOLOGY)
    parser.add_argument("--caps-assessment-design", type=Path, default=DEFAULT_CAPS_ASSESSMENT_DESIGN)
    parser.add_argument("--design-law", type=Path, default=DEFAULT_DESIGN_LAW)
    parser.add_argument("--source-matrix", type=Path, default=DEFAULT_SOURCE_MATRIX)
    parser.add_argument("--knowledge-bank", type=Path, default=DEFAULT_KNOWLEDGE_BANK)
    parser.add_argument("--preferred-language", default="English")
    parser.add_argument("--caps-extract-chars", type=int, default=8000)
    parser.add_argument("--total-marks", type=int, default=0, help="Override all subject mark totals.")
    parser.add_argument("--duration", default="", help="Override all subject durations.")
    parser.add_argument("--duration-hours", type=int, default=2)
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--timeout", type=float, default=70.0)
    parser.add_argument("--max-tokens", type=int, default=9000)
    parser.add_argument("--limit", type=int, default=0, help="Optional first-N pack limit for smoke runs.")
    parser.add_argument("--continue-on-fail", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Reuse existing passed subject-term jobs in the output folder.")
    parser.add_argument("--sleep-between", type=float, default=0.0, help="Seconds to wait between subject-term packs.")
    args = parser.parse_args()
    manifest = run_batch(args)
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

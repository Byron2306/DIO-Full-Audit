#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.product_grade_gauntlet import run_product_grade_gauntlet  # noqa: E402
from products.professional_task_gauntlet import run_professional_task_gauntlet  # noqa: E402
from products.professional_evidence_projection import slug  # noqa: E402
from products.site_full_grade_bridge_v3 import run_site_full_grade_v3  # noqa: E402
from scripts.run_professional_evidence_multitier_53 import run as run_canonical_multitier  # noqa: E402


SCHEMA = "dio.portfolio.production_gauntlet_receipt.v2"
MEASURED_TOKEN = "DIO_PORTFOLIO_PRODUCTION_GAUNTLET_57_MEASURED"
VERIFIED_TOKEN = "DIO_PORTFOLIO_PRODUCTION_GAUNTLET_57_ENGINEERING_VERIFIED"
CANONICAL_COUNT = 53
CANONICAL_VARIANTS = 3
CANONICAL_JOURNEYS = CANONICAL_COUNT * CANONICAL_VARIANTS
STUDIO_IDS = (
    "site_studio",
    "professional_correspondence_studio",
    "finance_readiness_studio",
    "article_publication_studio",
)
STUDIO_NAMES = {
    "site_studio": "Site Studio",
    "professional_correspondence_studio": "Professional Correspondence Studio",
    "finance_readiness_studio": "Finance Readiness Studio",
    "article_publication_studio": "Article & Publication Studio",
}
TOTAL_SURFACES = CANONICAL_COUNT + len(STUDIO_IDS)
HUMAN_ARTIFACT_SUFFIXES = {
    ".md", ".html", ".htm", ".txt", ".csv", ".pdf", ".docx", ".xlsx", ".pptx",
    ".svg", ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm", ".zip",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def load_crosswalk() -> dict[str, dict[str, str]]:
    path = ROOT / "config" / "atlas" / "dio_meta_incarnation_crosswalk.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {str(row["incarnation"]): dict(row) for row in csv.DictReader(handle)}


def phase(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    print(f"\n=== {name} ===", flush=True)
    started = utc_now()
    try:
        value = fn()
        return {"state": "COMPLETED", "started_at": started, "finished_at": utc_now(), "result": value}
    except Exception as exc:
        return {
            "state": "HARNESS_ERROR",
            "started_at": started,
            "finished_at": utc_now(),
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }


def run_pytest(paths: list[str]) -> dict[str, Any]:
    command = [sys.executable, "-m", "pytest", "-q", *paths]
    completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "passed": completed.returncode == 0,
    }
    if completed.returncode != 0:
        raise RuntimeError("pytest gate failed: " + " ".join(paths) + "\n" + completed.stdout[-5000:] + completed.stderr[-5000:])
    return result


def human_artifact_gate(canonical_root: Path, incarnation: str) -> dict[str, Any]:
    """Require a non-JSON, nontrivial execution artifact before buyer review is possible.

    This is deliberately weaker than ProductGrade. It answers only whether the normal
    customer journey emitted something a human can inspect without opening internal
    JSON receipts. Quality and willingness-to-use remain blind-review questions.
    """
    execution = canonical_root / "normal" / slug(incarnation) / "EXECUTION"
    candidates: list[dict[str, Any]] = []
    if execution.is_dir():
        for path in sorted(execution.rglob("*")):
            if not path.is_file() or path.stat().st_size < 100:
                continue
            if path.suffix.casefold() not in HUMAN_ARTIFACT_SUFFIXES:
                continue
            name = path.name.casefold()
            if "execution_error" in name:
                continue
            candidates.append(
                {
                    "path": str(path.relative_to(canonical_root)),
                    "bytes": path.stat().st_size,
                    "suffix": path.suffix.casefold(),
                }
            )
    return {
        "state": "PASS" if candidates else "REFUSE",
        "candidate_count": len(candidates),
        "candidates": candidates,
        "claim_boundary": "Presence of a human-readable execution artifact is a delivery-surface prerequisite, not a buyer-quality verdict.",
    }


def canonical_matrix(
    multitier_receipt: dict[str, Any],
    crosswalk: dict[str, dict[str, str]],
    canonical_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = []
    buyer_queue = []
    by_name = multitier_receipt.get("by_incarnation") or {}
    for incarnation, source in crosswalk.items():
        tier = by_name.get(incarnation) or {}
        journey_pass = tier.get("all_variants_verified") is True
        verified_count = int(tier.get("verified_count") or 0)
        deliverable = human_artifact_gate(canonical_root, incarnation)
        deliverable_pass = deliverable["state"] == "PASS"

        if not journey_pass:
            production_status = "REFUSE_MULTITIER_PIPELINE"
            reason = f"Normal/messy/adversarial Vesper-first journeys verified {verified_count}/{CANONICAL_VARIANTS}."
        elif not deliverable_pass:
            production_status = "REFUSE_NO_HUMAN_DELIVERABLE"
            reason = "Three Vesper-first journeys passed, but the normal execution left no nontrivial human-readable customer artifact outside JSON."
        else:
            production_status = "NEEDS_BLIND_BUYER_ARTIFACT_REVIEW"
            reason = "Three Vesper-first journeys passed and a human-readable deliverable exists; buyer-facing quality still requires artifact review."
            buyer_queue.append(
                {
                    "surface": incarnation,
                    "source_family": source.get("primary_family"),
                    "terminal_artifact_kind": ((tier.get("variants") or {}).get("normal") or {}).get("terminal_artifact_kind"),
                    "candidate_artifacts": deliverable["candidates"],
                    "review_dimensions": {
                        "correctness_and_trust": "1-5",
                        "buyer_job_fidelity": "1-5",
                        "edit_burden": "1-5 (5 = little/no editing)",
                        "professional_presentation": "1-5",
                        "usefulness": "1-5",
                        "would_use": "yes/no",
                        "production_blocker": "free text",
                    },
                }
            )

        rows.append(
            {
                "surface": incarnation,
                "source_family": source.get("primary_family"),
                "crosswalk_maturity": source.get("source_maturity"),
                "execution_truth_class": source.get("execution_truth_class"),
                "multitier_v1": {
                    "state": "PASS" if journey_pass else "REFUSE",
                    "verified": f"{verified_count}/{CANONICAL_VARIANTS}",
                    "normal": ((tier.get("variants") or {}).get("normal") or {}).get("passed") is True,
                    "messy": ((tier.get("variants") or {}).get("messy") or {}).get("passed") is True,
                    "adversarial": ((tier.get("variants") or {}).get("adversarial") or {}).get("passed") is True,
                },
                "human_deliverable_gate": deliverable,
                "blind_buyer_artifact_review": "PENDING" if journey_pass and deliverable_pass else "NOT_ELIGIBLE",
                "production_status": production_status,
                "reason": reason,
            }
        )
    return rows, buyer_queue


def studio_matrix(
    product_grade: dict[str, Any],
    professional_tasks: dict[str, Any],
    site_visual: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    rows = []
    pg = product_grade.get("studios") or {}
    task_summary = professional_tasks.get("studio_summary") or {}
    for studio_id in STUDIO_IDS:
        grade = pg.get(studio_id) or {}
        tasks = task_summary.get(studio_id) or {}
        task_count = int(tasks.get("case_count") or 0)
        verified_tasks = int(tasks.get("verified_count") or 0)
        grade_pass = grade.get("status") == "PRODUCT_GRADE_VERIFIED"
        task_pass = task_count >= 3 and verified_tasks == task_count
        visual_pass = True
        visual_reason = "not_applicable"
        if studio_id == "site_studio":
            visual_pass = bool(
                site_visual
                and site_visual.get("format_core_visual_compositor") == "PASS"
                and site_visual.get("visual_projection_authority") == "DIO_FORMAT_CORE"
                and site_visual.get("gamma_layout_authority") == "REFUSE"
                and site_visual.get("gamma_text_authority") == "REFUSE"
            )
            visual_reason = "PASS" if visual_pass else "SITE_FORMAT_CORE_VISUAL_PRODUCTION_NOT_VERIFIED"
        ready = grade_pass and task_pass and visual_pass
        blockers = list(grade.get("critical_blockers") or [])
        if not grade_pass and not blockers:
            blockers.append("PRODUCT_GRADE_NOT_VERIFIED")
        if not task_pass:
            blockers.append(f"MULTITIER_TASK_COVERAGE_{verified_tasks}_OF_{task_count}")
        if not visual_pass:
            blockers.append(visual_reason)
        rows.append(
            {
                "surface": STUDIO_NAMES[studio_id],
                "studio_id": studio_id,
                "product_grade": grade.get("status") or "MISSING",
                "product_grade_score": grade.get("score"),
                "professional_task_verified": f"{verified_tasks}/{task_count}",
                "site_visual_grade": visual_reason,
                "production_status": "PRODUCTION_ENGINEERING_VERIFIED" if ready else "REFUSE_PRODUCTION_READY",
                "blockers": sorted(set(blockers)),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the DIO 57-surface production gauntlet: 159 canonical journeys, four Studio ProductGrade surfaces, LINGUA semantic diversity and Format Core Site production."
    )
    parser.add_argument("--output", type=Path, default=ROOT / "state" / "portfolio_production_gauntlet" / "latest")
    parser.add_argument("--online", action="store_true", help="Enable current public-signal retrieval where a canonical product requires it.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero for an actual implemented-gate failure. Pending human buyer reviews do not make the harness crash.")
    args = parser.parse_args()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    crosswalk = load_crosswalk()
    if len(crosswalk) != CANONICAL_COUNT:
        raise RuntimeError(f"Expected {CANONICAL_COUNT} canonical ATLAS incarnations, found {len(crosswalk)}")

    phases: dict[str, Any] = {}
    phases["format_core_visual_tests"] = phase(
        "FORMAT CORE VISUAL TESTS",
        lambda: run_pytest([
            "tests/test_format_core_visual_composer.py",
            "tests/test_format_core_site_visual_compositor.py",
        ]),
    )
    phases["lingua_semantic_portfolio"] = phase(
        "LINGUA MARKETING SEMANTIC PORTFOLIO",
        lambda: run_pytest(["tests/test_lingua_marketing_surface_portfolio.py"]),
    )
    canonical_root = output / "canonical_53_x3"
    phases["canonical_53_x3"] = phase(
        "53 CANONICAL PRODUCTS × NORMAL / MESSY / ADVERSARIAL",
        lambda: run_canonical_multitier(canonical_root, online=args.online),
    )
    phases["studio_product_grade"] = phase(
        "FOUR STUDIO PRODUCTGRADE",
        lambda: run_product_grade_gauntlet(output_dir=output / "studio_product_grade", root=ROOT),
    )
    phases["studio_professional_tasks"] = phase(
        "FOUR STUDIO NORMAL / MESSY / ADVERSARIAL TASKS",
        lambda: run_professional_task_gauntlet(output_dir=output / "studio_professional_tasks", root=ROOT),
    )
    phases["site_format_core_production"] = phase(
        "SITE STUDIO FORMAT CORE PRODUCTION",
        lambda: run_site_full_grade_v3(
            manifest_path=ROOT / "config" / "studio_harvest" / "site_studio.json",
            output_dir=output / "site_format_core_production",
            root=ROOT,
        ),
    )

    multitier = (phases["canonical_53_x3"].get("result") or {}) if phases["canonical_53_x3"]["state"] == "COMPLETED" else {}
    product_grade = (phases["studio_product_grade"].get("result") or {}) if phases["studio_product_grade"]["state"] == "COMPLETED" else {}
    professional_tasks = (phases["studio_professional_tasks"].get("result") or {}) if phases["studio_professional_tasks"]["state"] == "COMPLETED" else {}
    site_visual = (phases["site_format_core_production"].get("result") or {}) if phases["site_format_core_production"]["state"] == "COMPLETED" else None

    canonical_products, buyer_queue = canonical_matrix(multitier, crosswalk, canonical_root)
    studio_products = studio_matrix(product_grade, professional_tasks, site_visual)
    products = [*canonical_products, *studio_products]

    canonical_multitier_verified = sum(row["multitier_v1"]["state"] == "PASS" for row in canonical_products)
    canonical_deliverable_verified = sum(row["human_deliverable_gate"]["state"] == "PASS" for row in canonical_products)
    canonical_buyer_pending = sum(row["blind_buyer_artifact_review"] == "PENDING" for row in canonical_products)
    studio_ready = sum(row["production_status"] == "PRODUCTION_ENGINEERING_VERIFIED" for row in studio_products)

    pipeline_failures = [row for row in canonical_products if row["multitier_v1"]["state"] != "PASS"]
    deliverable_failures = [
        row for row in canonical_products
        if row["multitier_v1"]["state"] == "PASS" and row["human_deliverable_gate"]["state"] != "PASS"
    ]
    studio_refusals = [row for row in studio_products if row["production_status"] != "PRODUCTION_ENGINEERING_VERIFIED"]
    harness_errors = {key: row for key, row in phases.items() if row["state"] != "COMPLETED"}

    all_159 = (
        multitier.get("all_53_x3_verified") is True
        and int(multitier.get("journey_count") or 0) == CANONICAL_JOURNEYS
        and int(multitier.get("verified_journey_count") or 0) == CANONICAL_JOURNEYS
    )
    studio_gates_pass = studio_ready == len(STUDIO_IDS)
    implemented_gates_pass = not harness_errors and all_159 and studio_gates_pass

    # Human buyer review is intentionally not fabricated by code. The master cannot
    # mint portfolio-wide production readiness until all 53 canonical customer
    # artifacts have actually been reviewed and accepted on the buyer-facing surface.
    portfolio_engineering_verified = (
        implemented_gates_pass
        and canonical_buyer_pending == 0
        and not pipeline_failures
        and not deliverable_failures
    )

    write_json(
        output / "CANONICAL_BLIND_BUYER_REVIEW_QUEUE.json",
        {
            "schema": "dio.portfolio.canonical_blind_buyer_review_queue.v1",
            "generated_at": utc_now(),
            "surface_count": len(buyer_queue),
            "reviews_completed": 0,
            "reviews_pending": len(buyer_queue),
            "reviewer_should_not_grade_receipts": True,
            "items": buyer_queue,
            "claim_boundary": "This queue identifies buyer-reviewable artifacts. It does not contain a synthetic buyer verdict.",
        },
    )

    receipt = {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "acceptance_token": VERIFIED_TOKEN if portfolio_engineering_verified else MEASURED_TOKEN,
        "surface_count": TOTAL_SURFACES,
        "canonical_surface_count": CANONICAL_COUNT,
        "new_studio_surface_count": len(STUDIO_IDS),
        "canonical_journey_count": int(multitier.get("journey_count") or 0),
        "canonical_verified_journey_count": int(multitier.get("verified_journey_count") or 0),
        "canonical_multitier_verified_count": canonical_multitier_verified,
        "canonical_human_deliverable_count": canonical_deliverable_verified,
        "canonical_blind_buyer_reviews_pending": canonical_buyer_pending,
        "new_studio_production_engineering_verified_count": studio_ready,
        "implemented_gates_pass": implemented_gates_pass,
        "portfolio_engineering_verified": portfolio_engineering_verified,
        "commercial_validation": "UNPROVED",
        "verified_payment": "UNPROVED",
        "repeatable_customer_acceptance": "UNPROVED",
        "phases": phases,
        "products": products,
        "kill_lists": {
            "canonical_multitier_failures": pipeline_failures,
            "canonical_customer_deliverable_failures": deliverable_failures,
            "new_studio_production_refusals": studio_refusals,
            "harness_errors": harness_errors,
        },
        "blind_buyer_review_queue": str(output / "CANONICAL_BLIND_BUYER_REVIEW_QUEUE.json"),
        "authority_created": False,
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "claim_boundary": (
            "This gauntlet runs 53 canonical incarnations through normal, messy and adversarial Vesper-first journeys, "
            "requires a human-readable normal-run execution artifact, runs the four newer Studios through ProductGrade and "
            "normal/messy/adversarial professional tasks, validates portfolio-wide LINGUA cross-surface semantic distance, "
            "and produces Site Studio through the Format Core visual path. Code does not invent blind buyer acceptance, payment, "
            "market demand or commercial validation."
        ),
    }
    write_json(output / "PORTFOLIO_PRODUCTION_GAUNTLET_RECEIPT.json", receipt)

    summary = {
        "acceptance_token": receipt["acceptance_token"],
        "surface_count": TOTAL_SURFACES,
        "canonical_journeys": f"{receipt['canonical_verified_journey_count']}/{CANONICAL_JOURNEYS}",
        "canonical_products_3_of_3": canonical_multitier_verified,
        "canonical_products_with_human_deliverable": canonical_deliverable_verified,
        "canonical_blind_buyer_reviews_pending": canonical_buyer_pending,
        "new_studios_production_engineering_verified": f"{studio_ready}/{len(STUDIO_IDS)}",
        "implemented_gates_pass": implemented_gates_pass,
        "portfolio_engineering_verified": portfolio_engineering_verified,
        "receipt": str(output / "PORTFOLIO_PRODUCTION_GAUNTLET_RECEIPT.json"),
        "buyer_review_queue": str(output / "CANONICAL_BLIND_BUYER_REVIEW_QUEUE.json"),
    }
    print("\n=== DIO PORTFOLIO PRODUCTION GAUNTLET SUMMARY ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.strict and not implemented_gates_pass:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

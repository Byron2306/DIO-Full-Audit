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
from products.site_full_grade_bridge_v3 import run_site_full_grade_v3  # noqa: E402
from scripts.run_professional_evidence_portfolio import run_portfolio  # noqa: E402


SCHEMA = "dio.portfolio.production_gauntlet_receipt.v1"
MEASURED_TOKEN = "DIO_PORTFOLIO_PRODUCTION_GAUNTLET_57_MEASURED"
VERIFIED_TOKEN = "DIO_PORTFOLIO_PRODUCTION_GAUNTLET_57_ENGINEERING_VERIFIED"
CANONICAL_COUNT = 53
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
        return {"state": "PASS", "started_at": started, "finished_at": utc_now(), "result": value}
    except Exception as exc:  # keep the whole gauntlet running so one failure cannot hide the rest
        return {
            "state": "FAIL",
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
        raise RuntimeError("pytest gate failed: " + " ".join(paths) + "\n" + completed.stdout[-4000:] + completed.stderr[-4000:])
    return result


def _canonical_matrix(evidence_receipt: dict[str, Any], crosswalk: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    rows = []
    by_name = {str(row.get("incarnation")): row for row in evidence_receipt.get("results") or []}
    for incarnation in crosswalk:
        execution = by_name.get(incarnation) or {}
        pipeline_pass = execution.get("status") == "PASS_FULL_PIPELINE"
        rows.append(
            {
                "surface": incarnation,
                "source_family": crosswalk[incarnation].get("primary_family"),
                "crosswalk_maturity": crosswalk[incarnation].get("source_maturity"),
                "execution_truth_class": crosswalk[incarnation].get("execution_truth_class"),
                "full_pipeline": "PASS" if pipeline_pass else "FAIL",
                "product_grade_tiers": "NOT_YET_DEFINED",
                "production_status": (
                    "NEEDS_PRODUCT_GRADE_TIER_COVERAGE" if pipeline_pass else "PIPELINE_FAILURE"
                ),
                "reason": (
                    "The literal-customer Vesper-to-product journey passed, but normal/messy/adversarial ProductGrade coverage is not yet defined for this canonical incarnation."
                    if pipeline_pass
                    else str(execution.get("error") or "Full professional customer pipeline did not pass.")
                ),
            }
        )
    return rows


def _studio_matrix(
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
        description="Run the complete DIO product-family production gauntlet across 53 canonical incarnations plus four current Studio surfaces."
    )
    parser.add_argument("--output", type=Path, default=ROOT / "state" / "portfolio_production_gauntlet" / "latest")
    parser.add_argument("--online", action="store_true", help="Enable current public-signal retrieval where a canonical product requires it.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero unless every currently defined engineering gate passes.")
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
    phases["canonical_53"] = phase(
        "53 CANONICAL PROFESSIONAL CUSTOMER JOURNEYS",
        lambda: run_portfolio(output / "canonical_53", online=args.online),
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

    canonical_receipt = (phases["canonical_53"].get("result") or {}) if phases["canonical_53"]["state"] == "PASS" else {}
    product_grade = (phases["studio_product_grade"].get("result") or {}) if phases["studio_product_grade"]["state"] == "PASS" else {}
    professional_tasks = (phases["studio_professional_tasks"].get("result") or {}) if phases["studio_professional_tasks"]["state"] == "PASS" else {}
    site_visual = (phases["site_format_core_production"].get("result") or {}) if phases["site_format_core_production"]["state"] == "PASS" else None

    canonical_products = _canonical_matrix(canonical_receipt, crosswalk)
    studio_products = _studio_matrix(product_grade, professional_tasks, site_visual)
    products = [*canonical_products, *studio_products]

    canonical_pipeline_verified = sum(row["full_pipeline"] == "PASS" for row in canonical_products)
    production_ready = [row for row in products if row["production_status"] in {"PRODUCTION_ENGINEERING_VERIFIED"}]
    pipeline_failures = [row for row in canonical_products if row["full_pipeline"] != "PASS"]
    coverage_gaps = [row for row in canonical_products if row["production_status"] == "NEEDS_PRODUCT_GRADE_TIER_COVERAGE"]
    studio_refusals = [row for row in studio_products if row["production_status"] != "PRODUCTION_ENGINEERING_VERIFIED"]

    all_defined_gates_pass = all(row["state"] == "PASS" for row in phases.values())
    all_53_pipeline = canonical_pipeline_verified == CANONICAL_COUNT and bool(canonical_receipt.get("all_full_pipeline_verified"))
    four_studios_ready = len(studio_refusals) == 0 and len(studio_products) == len(STUDIO_IDS)

    # Production truth is intentionally stricter than current test coverage. The 53
    # canonical incarnations need normal/messy/adversarial ProductGrade cases before
    # the master receipt may call the entire 57-surface family production verified.
    portfolio_engineering_verified = (
        all_defined_gates_pass
        and all_53_pipeline
        and four_studios_ready
        and not coverage_gaps
        and not pipeline_failures
    )

    receipt = {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "acceptance_token": VERIFIED_TOKEN if portfolio_engineering_verified else MEASURED_TOKEN,
        "surface_count": TOTAL_SURFACES,
        "canonical_surface_count": CANONICAL_COUNT,
        "new_studio_surface_count": len(STUDIO_IDS),
        "all_defined_gates_pass": all_defined_gates_pass,
        "canonical_full_pipeline_verified_count": canonical_pipeline_verified,
        "canonical_product_grade_tier_coverage_count": 0,
        "production_engineering_verified_count": len(production_ready),
        "portfolio_engineering_verified": portfolio_engineering_verified,
        "commercial_validation": "UNPROVED",
        "verified_payment": "UNPROVED",
        "repeatable_customer_acceptance": "UNPROVED",
        "phases": phases,
        "products": products,
        "kill_lists": {
            "pipeline_failures": pipeline_failures,
            "canonical_product_grade_coverage_gaps": coverage_gaps,
            "studio_production_refusals": studio_refusals,
        },
        "next_required_coverage": {
            "canonical_53": "Add normal, messy and adversarial ProductGrade cases for every canonical incarnation. Full-pipeline PASS alone cannot mint PRODUCTION_READY.",
            "commercial": "Observe real customer acceptance/payment separately. Engineering verification never invents market validation.",
        },
        "authority_created": False,
        "external_publication": "REFUSE",
        "external_send": "REFUSE",
        "media_spend": "REFUSE",
        "claim_boundary": (
            "This gauntlet measures engineering production readiness across the current DIO product family. "
            "A canonical full-pipeline PASS proves literal customer bytes reached a real bounded product executor, "
            "but the master gauntlet refuses PRODUCTION_READY until the same incarnation also has normal/messy/adversarial "
            "ProductGrade coverage. Commercial validation, willingness to pay and customer acceptance remain separately unproved."
        ),
    }
    write_json(output / "PORTFOLIO_PRODUCTION_GAUNTLET_RECEIPT.json", receipt)

    summary = {
        "acceptance_token": receipt["acceptance_token"],
        "surface_count": receipt["surface_count"],
        "canonical_full_pipeline_verified_count": canonical_pipeline_verified,
        "production_engineering_verified_count": len(production_ready),
        "canonical_product_grade_coverage_gaps": len(coverage_gaps),
        "pipeline_failures": len(pipeline_failures),
        "studio_production_refusals": len(studio_refusals),
        "receipt": str(output / "PORTFOLIO_PRODUCTION_GAUNTLET_RECEIPT.json"),
    }
    print("\n=== PORTFOLIO PRODUCTION GAUNTLET SUMMARY ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.strict and not portfolio_engineering_verified:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

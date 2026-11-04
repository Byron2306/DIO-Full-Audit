"""Build a source-bound HOMS Assess excerpt-retrieval review surface from a held run."""
from __future__ import annotations

import csv
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from products.homs_assess_customer import build_pointwise_educator_review

RUNS = ROOT / "acceptance_runs/68-product-sellability-20261027"
SOURCE_RUN = RUNS / "HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261102_G10_V31_GRANITE33_DEFAULT"
OUTPUT = RUNS / "HOMS_ASSESS_POINTWISE_QUOTE_SUGGESTIONS_20261102_V1"
EVIDENCE = RUNS / "HOMS_ASSESS_POINTWISE_QUOTE_SUGGESTIONS_20261102_V1.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    global SOURCE_RUN, OUTPUT, EVIDENCE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", default=SOURCE_RUN.name,
                        help="customer route folder under acceptance_runs/68-product-sellability-20261027")
    parser.add_argument("--output-suffix", default="20261102_V1",
                        help="new output suffix; output directories must not already exist")
    args = parser.parse_args()
    if not re.fullmatch(r"HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_[A-Z0-9_]+", args.source_run):
        raise ValueError("source-run must name a HOMS Assess customer execution directory")
    if not re.fullmatch(r"[A-Z0-9_]+", args.output_suffix):
        raise ValueError("output suffix may contain only uppercase letters, digits, and underscores")
    SOURCE_RUN = RUNS / args.source_run
    OUTPUT = RUNS / f"HOMS_ASSESS_POINTWISE_QUOTE_SUGGESTIONS_{args.output_suffix}"
    EVIDENCE = RUNS / f"HOMS_ASSESS_POINTWISE_QUOTE_SUGGESTIONS_{args.output_suffix}.json"
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise ValueError(f"output directory must be new or empty: {OUTPUT}")
    package_path = SOURCE_RUN / "CUSTOMER_PACKAGE_RECEIPT.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    input_dir = SOURCE_RUN / "input"
    results_path = SOURCE_RUN / package["outputs"]["results"]
    if not results_path.is_file():
        candidates = sorted((SOURCE_RUN / "hymark").glob("*/results.json"))
        if len(candidates) != 1:
            raise FileNotFoundError("Expected exactly one bound HOMS Assess result file")
        results_path = candidates[0]
    rubric_path = input_dir / "rubric.json"
    rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
    results_before = results_path.read_bytes()
    results = json.loads(results_before)
    if any(row.get("total_score") is not None or row.get("score_issued") is True for row in results):
        raise ValueError("The source run must remain held before building an educator suggestion surface")
    review = build_pointwise_educator_review(
        input_dir,
        rubric,
        results,
        results_path,
        OUTPUT,
        customer_packet_fingerprint=str(package.get("customer_packet_fingerprint") or ""),
    )
    if results_path.read_bytes() != results_before:
        raise ValueError("Review-surface generation changed the source score results")
    rows = list(csv.DictReader(review["adjudication_path"].open(encoding="utf-8-sig", newline="")))
    source_index = {}
    for student in results:
        path = input_dir / "uploads" / str(student["submission_file"])
        raw = path.read_bytes()
        source_index[str(student["student_id"])] = (path, raw, raw.decode("utf-8"))
    suggestion_count = 0
    points_with_suggestions = 0
    for row in rows:
        suggestions = json.loads(row["exact_question_source_quote_suggestions_json"] or "[]")
        if not suggestions:
            continue
        points_with_suggestions += 1
        path, raw, text = source_index[row["student_id"]]
        answer_hash = row["missing_point_answer_sha256"]
        excerpt = row["missing_point_answer_source_excerpt"]
        if not excerpt or hashlib.sha256(excerpt.encode("utf-8")).hexdigest() != answer_hash:
            raise ValueError("Suggestion row is not bound to a hash-verified question answer block")
        if sha(path) != row["missing_point_source_file_sha256"]:
            raise ValueError("Suggestion row is not bound to the original learner submission hash")
        for suggestion in suggestions:
            value = suggestion.get("text", "")
            if (suggestion.get("not_verified_as_point_evidence") is not True
                    or suggestion.get("answer_block_sha256") != answer_hash
                    or suggestion.get("source_file_sha256") != sha(path)
                    or " ".join(value.split()) not in " ".join(excerpt.split())):
                raise ValueError("A suggested excerpt is not an exact span in its bound question answer")
            suggestion_count += 1
        if any(row.get(field) for field in (
            "educator_verified_source_quote", "educator_verified_marks", "educator_decision",
            "educator_rationale", "educator_reviewer", "reviewed_at",
        )):
            raise ValueError("Suggestion surface unexpectedly populated an educator decision field")
    if sha(results_path) != hashlib.sha256(results_before).hexdigest():
        raise ValueError("Source results hash changed during review-surface generation")
    evidence = {
        "schema": "dio.homs.assess.pointwise_quote_suggestion_demo.v1",
        "product": "HOMS Assess",
        "source_run": str(SOURCE_RUN.relative_to(ROOT)),
        "source_results_sha256": hashlib.sha256(results_before).hexdigest(),
        "source_package_sha256": sha(package_path),
        "source_rubric_sha256": sha(rubric_path),
        "customer_packet_fingerprint": package.get("customer_packet_fingerprint"),
        "submission_count": len(results),
        "source_totals_all_withheld": all(row.get("total_score") is None for row in results),
        "suggested_exact_question_scoped_span_count": suggestion_count,
        "points_with_suggestions": points_with_suggestions,
        "suggestions_are_unverified_not_scoring_evidence": True,
        "suggestions_bound_to_answer_block_and_source_hashes": True,
        "educator_decision_fields_blank": True,
        "source_results_unchanged": True,
        "score_mutation_performed": False,
        "classroom_release_authorized": False,
        "outputs": {
            "review_page": str(review["path"].relative_to(ROOT)),
            "review_page_sha256": sha(review["path"]),
            "adjudication_csv": str(review["adjudication_path"].relative_to(ROOT)),
            "adjudication_csv_sha256": sha(review["adjudication_path"]),
            "review_receipt": str(review["receipt_path"].relative_to(ROOT)),
            "review_receipt_sha256": sha(review["receipt_path"]),
            "educator_guide": str(OUTPUT.joinpath("EDUCATOR_POINTWISE_ADJUDICATION_GUIDE.md").relative_to(ROOT)),
            "educator_guide_sha256": sha(OUTPUT / "EDUCATOR_POINTWISE_ADJUDICATION_GUIDE.md"),
            "quality_flags_csv": str(review["quality_flags_path"].relative_to(ROOT)),
            "quality_flags_csv_sha256": sha(review["quality_flags_path"]),
        },
        "interpretation": "Exact sentence retrieval narrows educator reading to the source-bound answer block. Lexical overlap does not prove a point is correct; suggestions never become model quotes or marks and do not unblock totals.",
    }
    EVIDENCE.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"evidence": str(EVIDENCE.relative_to(ROOT)), "suggestions": suggestion_count,
                      "points_with_suggestions": points_with_suggestions,
                      "source_totals_all_withheld": evidence["source_totals_all_withheld"]}, indent=2))


if __name__ == "__main__":
    main()

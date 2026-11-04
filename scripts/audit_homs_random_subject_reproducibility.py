#!/usr/bin/env python3
"""Reconstruct and document the seeded CAPS-phase subject assignment draw."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "deliverables/homs_random_grade_exam_set_20261101"
ASSIGNMENTS = PACK / "RANDOM_SUBJECT_ASSIGNMENTS.json"
IDENTITIES = PACK / "RANDOM_SUBJECT_CAPS_DOCUMENT_IDENTITY_AUDIT_20261101.json"
GENERATOR = ROOT / "scripts/build_homs_random_grade_exam_set.py"
OUTPUT = PACK / "RANDOM_SUBJECT_REPRODUCIBILITY_AUDIT_20261102.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    spec = importlib.util.spec_from_file_location("homs_random_grade_exam_set", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the subject-assignment generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assignment_doc = json.loads(ASSIGNMENTS.read_text(encoding="utf-8"))
    identity_doc = json.loads(IDENTITIES.read_text(encoding="utf-8"))
    seed = int(assignment_doc["random_seed"])
    actual = assignment_doc.get("assignments", [])
    reconstructed = module.phase_randomization(seed)
    by_phase: dict[str, list[dict]] = defaultdict(list)
    for row in actual:
        by_phase[str(row["phase"])].append(row)
    phase_audits = []
    phase_pools = module.PHASE_SUBJECTS
    for phase, grades in module.PHASES.items():
        phase_rows = sorted(by_phase.get(phase, []), key=lambda row: int(row["grade"]))
        pool = list(phase_pools[phase])
        subjects = [str(row["subject_profile"]) for row in phase_rows]
        phase_audits.append({
            "phase": phase,
            "grades": grades,
            "approved_subject_pool": pool,
            "assigned_subjects": subjects,
            "no_replacement_satisfied": len(subjects) == len(set(subjects)),
            "all_assignments_in_pool": all(subject in pool for subject in subjects),
            "reconstructed_rows_match": phase_rows == [row for row in reconstructed if row["phase"] == phase],
        })
    identity_by_grade = {int(row["grade"]): row for row in identity_doc.get("grades", [])}
    identity_matches = all(
        int(row["grade"]) in identity_by_grade
        and identity_by_grade[int(row["grade"])].get("randomized_subject_profile") == row.get("subject_profile")
        and identity_by_grade[int(row["grade"])].get("assignment_phase") == row.get("phase")
        and identity_by_grade[int(row["grade"])].get("source_identity_check") == "PASS_SUBJECT_FILENAME_AND_HASH_MATCH"
        for row in actual
    )
    complete = (
        len(actual) == 12
        and actual == reconstructed
        and all(row["no_replacement_satisfied"] and row["all_assignments_in_pool"]
                and row["reconstructed_rows_match"] for row in phase_audits)
        and identity_matches
        and identity_doc.get("all_hashes_verified_in_caps_manifest") is True
    )
    report = {
        "schema": "dio.homs.random_subject_reproducibility_audit.v1",
        "seed": seed,
        "rng": "Python random.Random(seed), Mersenne Twister, sequential phase iteration and list.shuffle calls as implemented in the recorded generator",
        "python_version": platform.python_version(),
        "assignment_manifest": {"path": ASSIGNMENTS.relative_to(ROOT).as_posix(), "sha256": sha(ASSIGNMENTS)},
        "generator": {"path": GENERATOR.relative_to(ROOT).as_posix(), "sha256": sha(GENERATOR)},
        "caps_identity_audit": {"path": IDENTITIES.relative_to(ROOT).as_posix(), "sha256": sha(IDENTITIES)},
        "phase_results": phase_audits,
        "assignment_draw_reconstructed": actual == reconstructed,
        "caps_identity_rows_match_assignments": identity_matches,
        "all_source_caps_hashes_verified": identity_doc.get("all_hashes_verified_in_caps_manifest") is True,
        "result": "PASS" if complete else "REVIEW_REQUIRED",
        "educator_review_required": True,
        "classroom_release_authorized": False,
    }
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"result": report["result"], "seed": seed, "phase_count": len(phase_audits),
                      "grade_count": len(actual), "assignment_manifest_sha256": sha(ASSIGNMENTS),
                      "caps_identity_rows_match_assignments": identity_matches}, indent=2))
    if not complete:
        raise SystemExit("randomized subject assignment could not be independently reconstructed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

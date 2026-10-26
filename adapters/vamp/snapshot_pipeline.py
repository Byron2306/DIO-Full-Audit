from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

from adapters.evidence_kernel import EvidenceConfidence, InstitutionalProfile, load_profile
from sovereign_runtime import evidex_environment, evidex_root, ollama_model, ollama_url


ROOT = Path(__file__).resolve().parents[2]
REQUEST_SCHEMA = ROOT / "schemas" / "vamp_snapshot_request.schema.json"
EVIDENCE_SCHEMA = ROOT / "schemas" / "evidence_record_v2.schema.json"
EVIDEX_ROOT = evidex_root()
EVIDEX_PYTHON = EVIDEX_ROOT / ".venv" / "bin" / "python"
REQUIRED_TABLES = {"evidence", "evidence_task", "tasks", "task_no_evidence"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def open_readonly_database(path: Path) -> sqlite3.Connection:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"VAMP database not found: {resolved}")
    connection = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = REQUIRED_TABLES - tables
    if missing:
        connection.close()
        raise ValueError(f"VAMP database is missing required tables: {', '.join(sorted(missing))}")
    return connection


def _safe_meta(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _matched_terms(reason: str, profile: InstitutionalProfile) -> list[str]:
    match = re.search(r"(?:with terms|evidence signals):\s*([^|]+)", reason or "", re.IGNORECASE)
    if not match:
        return []
    terms = [re.sub(r"[^a-z0-9_-]", "", item.lower()).strip("_-") for item in match.group(1).split(",")]
    return sorted({term for term in terms if len(term) > 2 and term not in profile.stopwords})


def _identifiers(text: str, profile: InstitutionalProfile) -> set[str]:
    pattern = str(profile.data["mapping_policy"]["identifier_pattern"])
    return {re.sub(r"[ -]", "", item.upper()) for item in re.findall(pattern, text or "")}


def _source_kind(meta: dict[str, Any], mapped_by: str) -> str:
    outlook = meta.get("outlook") if isinstance(meta.get("outlook"), dict) else {}
    if outlook.get("source"):
        return str(outlook["source"])
    if mapped_by.startswith("efundi"):
        return "lms"
    if "outlook" in mapped_by:
        return "outlook"
    if "human" in mapped_by:
        return "human_review"
    return "registered_file"


def _verify_source_integrity(file_path: Path, registered_sha1: str) -> tuple[bool, str]:
    """Verify registered SHA-1 against actual source bytes.

    SHA-1 is a legacy compatibility identifier, not a modern
    collision-resistant security attestation.
    """
    if not re.fullmatch(r"[0-9a-fA-F]{40}", registered_sha1):
        return False, "Source integrity REFUSE: missing or malformed SHA-1."

    if not file_path.is_file():
        return False, "Source integrity REFUSE: registered file missing."

    digest = hashlib.sha1()
    try:
        with file_path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return False, "Source integrity REFUSE: source unreadable."

    if not __import__('hmac').compare_digest(digest.hexdigest(), registered_sha1.lower()):
        return False, "Source integrity REFUSE: SHA-1 mismatch."

    return True, "Source integrity verified against registered SHA-1."


def calibrate_mapping(
    *,
    profile: InstitutionalProfile,
    evidence: sqlite3.Row,
    task: sqlite3.Row,
    mapping: sqlite3.Row,
    duplicate_of: str | None,
) -> tuple[EvidenceConfidence, str, list[str]]:
    meta = _safe_meta(str(evidence["meta_json"] or "{}"))
    mapped_by = str(mapping["mapped_by"] or "")
    human_asserted = "human" in mapped_by or "asserted" in mapped_by
    reasons: list[str] = []

    if human_asserted and profile.data["mapping_policy"]["human_assertion_precedence"]:
        retrieval = relevance = 1.0
        reasons.append("Human-confirmed mapping takes precedence.")
    elif mapped_by.startswith("efundi_collect:direct_lms"):
        retrieval, relevance = 0.98, 0.95
        reasons.append("Direct LMS collection with an explicit task mapping.")
    elif "outlook" in mapped_by:
        retrieval, relevance = 0.92, 0.35
        reasons.append("Targeted Outlook collection; semantic relevance recalibrated independently.")
    else:
        retrieval, relevance = 0.75, min(0.9, float(mapping["confidence"] or 0.5))

    file_path = Path(str(evidence["file_path"] or ""))
    sha1 = str(evidence["sha1"] or "")
    integrity_ok, integrity_reason = _verify_source_integrity(file_path, sha1)
    provenance = 1.0 if integrity_ok else 0.0
    reasons.append(integrity_reason)

    outlook = meta.get("outlook") if isinstance(meta.get("outlook"), dict) else {}
    search_reason = str(outlook.get("search_reason") or "")
    terms = _matched_terms(search_reason, profile)
    evidence_ids = _identifiers(f"{file_path.name} {search_reason}", profile)
    task_ids = _identifiers(str(task["title"] or ""), profile)
    shared_ids = evidence_ids & task_ids
    if not human_asserted and not mapped_by.startswith("efundi_collect:direct_lms"):
        if shared_ids:
            relevance = 0.92
            reasons.append("Shared objective identifier: " + ", ".join(sorted(shared_ids)) + ".")
        elif len(terms) >= 3:
            relevance = 0.86
            reasons.append(f"{len(terms)} meaningful mapping terms matched.")
        elif len(terms) == 2:
            relevance = 0.76
            reasons.append("Two meaningful mapping terms matched.")
        elif len(terms) == 1:
            relevance = 0.58
            reasons.append(f"Only one meaningful mapping term matched: {terms[0]}.")
        else:
            relevance = 0.35
            reasons.append("No meaningful mapping terms survived calibration.")

        target_task = str(meta.get("target_task_id") or "")
        if target_task and target_task == str(task["task_id"]):
            relevance = min(0.95, relevance + 0.04)
        brain = meta.get("brain") if isinstance(meta.get("brain"), dict) else {}
        brain_kpa = str(brain.get("primary_kpa_code") or "")
        if brain_kpa and brain_kpa == str(task["kpa_code"]):
            relevance = min(0.95, relevance + 0.04)
            reasons.append("Automated domain route agrees with the objective domain.")
        elif brain_kpa:
            relevance = max(0.2, relevance - 0.15)
            reasons.append("Automated domain route conflicts with the objective domain.")

    cue_text = f"{file_path.name} {search_reason}".lower()
    strong = sorted({cue for cue in profile.strong_cues if cue in cue_text})
    weak = sorted({cue for cue in profile.weak_cues if cue in cue_text})
    if human_asserted:
        sufficiency = 0.9
    elif weak and not strong:
        sufficiency = 0.35
        reasons.append("Weak source form: " + ", ".join(weak[:3]) + ".")
    elif strong:
        sufficiency = 0.86
        reasons.append("Substantive source cues: " + ", ".join(strong[:3]) + ".")
    else:
        sufficiency = 0.6
        reasons.append("Source may be relevant but sufficiency needs human confirmation.")

    confidence = EvidenceConfidence(
        retrieval=round(retrieval, 3),
        relevance=round(relevance, 3),
        provenance=round(provenance, 3),
        sufficiency=round(sufficiency, 3),
    )
    if not integrity_ok:
        return confidence, "candidate", reasons + [
            "Integrity failure blocks accepted evidence coverage."
        ]
    if duplicate_of:
        return confidence, "duplicate_suppressed", reasons + [f"Duplicate hash already represented by {duplicate_of}."]
    thresholds = profile.thresholds
    accepted = all(getattr(confidence, key) >= threshold for key, threshold in thresholds.items())
    return confidence, "accepted" if accepted else "candidate", reasons


def _query_rows(connection: sqlite3.Connection, sql: str, parameters: tuple[Any, ...]) -> list[sqlite3.Row]:
    return list(connection.execute(sql, parameters))


def _source_display(index: int, path: str, privacy_mode: str) -> str:
    return Path(path).name if privacy_mode == "private_internal" else f"Evidence {index:03d}"


def _markdown_summary(snapshot: dict[str, Any]) -> str:
    metrics = snapshot["metrics"]
    domain_lines = "\n".join(
        f"| {item['label']} | {item['objectives']} | {item['evidence_backed']} | {item['partial']} | {item['declared_no_evidence']} | {item['gaps']} |"
        for item in snapshot["domains"]
    )
    return f"""# VAMP Performance Evidence Snapshot

Profile: `{snapshot['profile']['profile_id']}`  
Review period: {', '.join(snapshot['review']['months'])}

## Coverage

- Objectives in period: **{metrics['objectives_total']}**
- Evidence-backed objectives: **{metrics['objectives_evidence_backed']}** ({metrics['evidence_backed_pct']:.1f}%)
- Partially supported objectives: **{metrics['objectives_partial']}**
- Declared no-evidence objectives: **{metrics['objectives_declared_no_evidence']}**
- Open gaps: **{metrics['objectives_gap']}**
- Accepted mappings: **{metrics['accepted_mappings']}**
- Candidate mappings requiring review: **{metrics['candidate_mappings']}**
- Duplicate evidence records suppressed: **{metrics['duplicates_suppressed']}**

This is evidence-coverage support, not an employee rating or employment decision.

## Domains

| Domain | Objectives | Backed | Partial | Declared no evidence | Gaps |
|---|---:|---:|---:|---:|---:|
{domain_lines}

## Release Gates

{chr(10).join(f"- [{'x' if gate['passed'] else ' '}] {gate['name']}: {gate['detail']}" for gate in snapshot['quality_gates'])}
"""


def _build_vamp_evidex_handoff(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Preserve VAMP decisions without promoting derived summaries to evidence."""
    objectives = {
        item["objective_id"]: item
        for item in snapshot["objectives"]
    }
    links = []

    for record in snapshot["evidence"]:
        for mapping in record["mappings"]:
            objective_id = mapping["objective_id"]
            if objective_id not in objectives:
                raise ValueError(
                    f"REFUSE: mapping references missing objective {objective_id}"
                )

            links.append({
                "objective_id": objective_id,
                "evidence_id": record["evidence_id"],
                "source_sha1": record["sha1"],
                "source": record["source"],
                "duplicate_of": record["duplicate_of"],
                "period": record["period"],
                "decision": mapping["decision"],
                "confidence": mapping["confidence"],
                "mapped_by": mapping["mapped_by"],
                "reasons": mapping["reasons"],
                "authority_scope": "vamp_calibration_only",
                "source_bytes_reverified": False,
                "customer_claim_independently_verified": False,
            })

    links.sort(key=lambda x: (
        x["objective_id"], x["evidence_id"], x["decision"]
    ))

    for objective_id, objective in objectives.items():
        accepted = {
            link["evidence_id"]
            for link in links
            if link["objective_id"] == objective_id
            and link["decision"] == "accepted"
            and link["duplicate_of"] is None
        }
        if len(accepted) != objective["accepted_evidence"]:
            raise ValueError(
                f"REFUSE: accepted mapping count mismatch for {objective_id}"
            )

    return {
        "schema": "dio.vamp_evidex_handoff.v1",
        "job_id": snapshot["job_id"],
        "snapshot_schema": snapshot["schema"],
        "review": snapshot["review"],
        "objectives": [
            {
                "objective_id": item["objective_id"],
                "minimum_required": item["minimum_required"],
                "accepted_evidence": item["accepted_evidence"],
                "candidate_evidence": item["candidate_evidence"],
                "coverage_status": item["coverage_status"],
            }
            for item in snapshot["objectives"]
        ],
        "source_mappings": links,
        "derived_ledger_summaries_are_primary_evidence": False,
        "source_bytes_reverified": False,
        "customer_claim_independently_verified": False,
        "human_review_required": True,
        "delivery_authorized": False,
    }


def _write_evidex_inputs(snapshot: dict[str, Any], job_dir: Path) -> tuple[Path, Path]:
    intake_dir = job_dir / "evidex_input"
    uploads_dir = intake_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    objectives = snapshot["objectives"]
    gaps = [item["title"] for item in objectives if item["coverage_status"] in {"gap", "declared_no_evidence"}]
    intake = {
        "client": {
            "organization": snapshot["profile"]["institution"],
            "contact_name": "Private controlled validation",
            "contact_email": None,
        },
        "pack": {
            "purpose": "Performance evidence readiness and review preparation",
            "donor": None,
            "project_name": f"VAMP evidence snapshot {snapshot['job_id']}",
            "grant_id": snapshot["job_id"],
            "reporting_period": {
                "start": snapshot["review"]["months"][0],
                "end": snapshot["review"]["months"][-1],
            },
            "tone": "conservative, evidence-led, human-reviewed",
            "include_appendix": False,
        },
        "kpis": [
            {
                # Evidex packages VAMP's calibrated decision. The immutable ID
                # prevents its broad KPI keyword matcher from cross-matching
                # similar recurring objectives in different months.
                "name": item["objective_id"],
                "target": item["minimum_required"],
                "actual": item["accepted_evidence"],
                "measurement": f"{item['title']} - accepted, provenance-registered evidence mappings",
            }
            for item in objectives
        ],
        "constraints": {
            "avoid_claims": [
                "Do not interpret evidence coverage as an employee rating.",
                "Do not treat candidate mappings as accepted evidence without human review.",
                "Do not make disciplinary, promotion, remuneration, or employment decisions from this pack.",
            ],
            "known_gaps": gaps[:50],
        },
        "billing": {
            "client_type": "performance_evidence",
            "quantity": 1,
            "currency": "USD",
            "service_name": "VAMP Performance Evidence Snapshot",
        },
    }
    intake_path = intake_dir / "intake.json"
    write_json(intake_path, intake)
    for item in objectives:
        if item["accepted_evidence"] <= 0:
            continue
        body = (
            f"Objective ID: {item['objective_id']}\n"
            f"Objective title: {item['title']}\n"
            f"Domain: {item['domain_code']}\n"
            f"Accepted evidence count: {item['accepted_evidence']}\n"
            f"Minimum required: {item['minimum_required']}\n"
            "Source details remain in the governed VAMP provenance ledger.\n"
        )
        (uploads_dir / f"{item['objective_id']}_evidence_ledger.txt").write_text(body, encoding="utf-8")
    return intake_path, uploads_dir


def _run_evidex(intake_path: Path, uploads_dir: Path, out_dir: Path) -> dict[str, Any]:
    if not EVIDEX_PYTHON.is_file():
        raise FileNotFoundError(f"Evidex Python not found: {EVIDEX_PYTHON}")
    env = evidex_environment()
    env.update({
        "OLLAMA_MODEL": ollama_model(),
        "OLLAMA_URL": ollama_url(),
        "LLM_DISABLED": "1",
        "SUMMARY_USE_LLM": "0",
        "NARRATIVE_USE_LLM": "0",
    })
    command = [
        str(EVIDEX_PYTHON), "-m", "evidence_pack_engine.cli", "generate",
        "--intake", str(intake_path), "--uploads", str(uploads_dir), "--out", str(out_dir),
    ]
    result = subprocess.run(command, cwd=EVIDEX_ROOT, env=env, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Evidex generation failed: {result.stderr.strip()}")
    return {"command": command, "returncode": result.returncode, "zip": result.stdout.strip().splitlines()[-1]}


def build_snapshot(request_path: Path, output_root: Path, *, run_evidex: bool = True) -> Path:
    request = read_json(request_path)
    jsonschema.validate(request, read_json(REQUEST_SCHEMA), format_checker=jsonschema.FormatChecker())
    profile_path = Path(request["profile_path"])
    if not profile_path.is_absolute():
        profile_path = (request_path.parent / profile_path).resolve()
    profile = load_profile(profile_path)
    months = sorted(set(request["review"]["months"]))
    job_id = str(request["job_id"])
    job_dir = output_root.expanduser().resolve() / job_id
    job_dir.mkdir(parents=True, exist_ok=False)

    db_path = Path(request["source"]["database_path"])
    connection = open_readonly_database(db_path)
    placeholders = ",".join("?" for _ in months)
    # Include objectives active during any requested review month.
    # A task beginning in January and ending in August belongs in
    # the August review, even though its start month is January.
    overlap = " OR ".join(
        "(substr(window_start,1,7) <= ? AND substr(window_end,1,7) >= ?)"
        for _ in months
    )
    tasks = _query_rows(
        connection,
        f"SELECT * FROM tasks WHERE ({overlap}) ORDER BY window_start,kpa_code,title",
        tuple(value for month in months for value in (month, month)),
    )
    task_map = {str(row["task_id"]): row for row in tasks}
    evidence = _query_rows(
        connection,
        f"SELECT * FROM evidence WHERE staff_id=? AND year=? AND month_bucket IN ({placeholders}) ORDER BY month_bucket,evidence_id",
        (request["source"]["staff_id"], request["source"]["year"], *months),
    )
    mappings = _query_rows(
        connection,
        f"SELECT et.* FROM evidence_task et JOIN evidence e USING(evidence_id) WHERE e.staff_id=? AND e.year=? AND e.month_bucket IN ({placeholders}) ORDER BY et.evidence_id,et.task_id",
        (request["source"]["staff_id"], request["source"]["year"], *months),
    )
    declarations = _query_rows(
        connection,
        f"SELECT * FROM task_no_evidence WHERE staff_id=? AND year=? AND month IN ({placeholders})",
        (request["source"]["staff_id"], request["source"]["year"], *months),
    )
    connection.close()

    mappings_by_evidence: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in mappings:
        if str(row["task_id"]) in task_map:
            mappings_by_evidence[str(row["evidence_id"])].append(row)
    declaration_ids = {str(row["task_id"]) for row in declarations}
    seen_hashes: dict[str, str] = {}
    evidence_schema = read_json(EVIDENCE_SCHEMA)
    normalized: list[dict[str, Any]] = []
    accepted_by_task: dict[str, set[str]] = defaultdict(set)
    candidate_by_task: dict[str, set[str]] = defaultdict(set)

    for index, row in enumerate(evidence, 1):
        evidence_id = str(row["evidence_id"])
        sha1 = str(row["sha1"] or "")
        duplicate_of = seen_hashes.get(sha1) if sha1 and profile.data["evidence_policy"]["deduplicate_by_hash"] else None
        if sha1 and not duplicate_of:
            seen_hashes[sha1] = evidence_id
        record_mappings: list[dict[str, Any]] = []
        for mapping in mappings_by_evidence.get(evidence_id, []):
            task = task_map[str(mapping["task_id"])]
            confidence, decision, reasons = calibrate_mapping(
                profile=profile, evidence=row, task=task, mapping=mapping, duplicate_of=duplicate_of
            )
            record_mappings.append({
                "objective_id": str(task["task_id"]),
                "mapped_by": str(mapping["mapped_by"]),
                "confidence": confidence.to_dict(),
                "decision": decision,
                "reasons": reasons,
            })
            target = accepted_by_task if decision == "accepted" else candidate_by_task
            if decision in {"accepted", "candidate"}:
                target[str(task["task_id"])].add(evidence_id)
        if duplicate_of:
            review_status = "duplicate_suppressed"
        elif any(item["decision"] == "accepted" for item in record_mappings):
            review_status = "accepted"
        elif record_mappings:
            review_status = "candidate"
        else:
            review_status = "unmapped"
        meta = _safe_meta(str(row["meta_json"] or "{}"))
        record = {
            "schema": "dio.evidence_record.v2",
            "evidence_id": evidence_id,
            "source": {
                "kind": _source_kind(meta, record_mappings[0]["mapped_by"] if record_mappings else ""),
                "display_name": _source_display(index, str(row["file_path"]), request["privacy_mode"]),
                "path_registered": Path(str(row["file_path"] or "")).is_file(),
            },
            "sha1": sha1,
            "period": str(row["month_bucket"]),
            "domain_code": str(row["kpa_code"] or ""),
            "duplicate_of": duplicate_of,
            "mappings": record_mappings,
            "review_status": review_status,
        }
        jsonschema.validate(record, evidence_schema)
        normalized.append(record)

    objectives: list[dict[str, Any]] = []
    for task in tasks:
        task_id = str(task["task_id"])
        accepted_count = len(accepted_by_task[task_id])
        candidate_count = len(candidate_by_task[task_id])
        minimum = max(1, int(task["min_required"] or 1))
        declared = task_id in declaration_ids
        if accepted_count >= minimum:
            status = "evidence_backed"
        elif accepted_count:
            status = "partial"
        elif declared:
            status = "declared_no_evidence"
        else:
            status = "gap"
        objectives.append({
            "objective_id": task_id,
            "domain_code": str(task["kpa_code"]),
            "title": str(task["title"]),
            "period": str(task["window_start"])[:7],
            "minimum_required": minimum,
            "accepted_evidence": accepted_count,
            "candidate_evidence": candidate_count,
            "declared_no_evidence": declared,
            "coverage_status": status,
        })

    objective_counts = Counter(item["coverage_status"] for item in objectives)
    mapping_counts = Counter(
        mapping["decision"] for record in normalized for mapping in record["mappings"]
    )
    domain_rows = []
    for code in sorted({item["domain_code"] for item in objectives}):
        rows = [item for item in objectives if item["domain_code"] == code]
        counts = Counter(item["coverage_status"] for item in rows)
        domain_rows.append({
            "code": code,
            "label": (profile.domain_map.get(code) or {}).get("label", code),
            "objectives": len(rows),
            "evidence_backed": counts["evidence_backed"],
            "partial": counts["partial"],
            "declared_no_evidence": counts["declared_no_evidence"],
            "gaps": counts["gap"],
        })
    metrics = {
        "evidence_records": len(normalized),
        "unique_hashes": len({item["sha1"] for item in normalized if item["sha1"]}),
        "objectives_total": len(objectives),
        "objectives_evidence_backed": objective_counts["evidence_backed"],
        "objectives_partial": objective_counts["partial"],
        "objectives_declared_no_evidence": objective_counts["declared_no_evidence"],
        "objectives_gap": objective_counts["gap"],
        "evidence_backed_pct": round(100.0 * objective_counts["evidence_backed"] / len(objectives), 1) if objectives else 0.0,
        "accepted_mappings": mapping_counts["accepted"],
        "candidate_mappings": mapping_counts["candidate"],
        "duplicates_suppressed": sum(1 for item in normalized if item["duplicate_of"]),
        "unmapped_evidence": sum(1 for item in normalized if item["review_status"] == "unmapped"),
    }
    gates = [
        {"name": "profile_validated", "passed": True, "detail": f"Loaded {profile.profile_id} {profile.data['version']}."},
        {"name": "source_read_only", "passed": True, "detail": "VAMP SQLite opened in read-only mode."},
        {"name": "ratings_disabled", "passed": not profile.data["rating_policy"]["enabled"], "detail": "Snapshot reports evidence coverage only."},
        {"name": "provenance_registered", "passed": all(item["sha1"] for item in normalized), "detail": "Every normalized record must retain a source hash."},
        {"name": "human_review_required", "passed": True, "detail": "Candidate mappings are withheld from evidence-backed coverage."},
    ]
    snapshot = {
        "schema": "dio.vamp_snapshot.v1",
        "job_id": job_id,
        "created_at": utc_now(),
        "profile": {
            "profile_id": profile.profile_id,
            "version": profile.data["version"],
            "institution": profile.data["institution"]["name"],
            "terminology": profile.data["terminology"],
        },
        "review": {"year": request["source"]["year"], "months": months, "privacy_mode": request["privacy_mode"]},
        "metrics": metrics,
        "domains": domain_rows,
        "objectives": objectives,
        "evidence": normalized,
        "quality_gates": gates,
        "release": {
            "status": "ready_for_human_review" if all(gate["passed"] for gate in gates) else "blocked",
            "rating_generated": False,
            "employment_decision_generated": False,
        },
    }
    write_json(job_dir / "VAMP_SNAPSHOT.json", snapshot)
    (job_dir / "VAMP_SNAPSHOT.md").write_text(_markdown_summary(snapshot), encoding="utf-8")
    write_json(job_dir / "EVIDENCE_LEDGER.json", normalized)
    write_json(job_dir / "OBJECTIVE_COVERAGE.json", objectives)
    handoff = _build_vamp_evidex_handoff(snapshot)
    handoff["snapshot_sha256"] = hashlib.sha256(
        (job_dir / "VAMP_SNAPSHOT.json").read_bytes()
    ).hexdigest()
    write_json(
        job_dir / "VAMP_EVIDEX_HANDOFF.json",
        handoff,
    )

    intake_path, uploads_dir = _write_evidex_inputs(snapshot, job_dir)
    evidex_receipt: dict[str, Any] = {"status": "not_run"}
    if run_evidex:
        evidex_out = job_dir / "evidex_output"
        evidex_out.mkdir(parents=True, exist_ok=True)
        evidex_receipt = {"status": "generated", **_run_evidex(intake_path, uploads_dir, evidex_out)}
    write_json(job_dir / "EVIDEX_COMPATIBILITY_RECEIPT.json", evidex_receipt)

    archive = job_dir / f"{job_id}_VAMP_EVIDENCE_SNAPSHOT.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(job_dir.rglob("*")):
            if path.is_file() and path != archive and "evidex_input/uploads" not in str(path.relative_to(job_dir)):
                handle.write(path, arcname=str(path.relative_to(job_dir)))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    write_json(job_dir / "VAMP_SNAPSHOT_RECEIPT.json", {
        "schema": "dio.vamp_snapshot_receipt.v1",
        "job_id": job_id,
        "created_at": utc_now(),
        "status": snapshot["release"]["status"],
        "archive": str(archive),
        "archive_sha256": digest,
        "metrics": metrics,
        "profile_id": profile.profile_id,
    })
    return job_dir

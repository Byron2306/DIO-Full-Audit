from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from adapters.beast_product_grade import BeastProductGradeError, run_beast_artifact_checks
from adapters.lingua.communicator import plain_text_from_html
from products.studio_customer_delivery import render_customer_delivery
from products.studio_native_closure import close_studio_case, verify_native_closure_proof

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_GRADE_THRESHOLD = 85
VERIFIED = "PRODUCT_GRADE_VERIFIED"
REFUSE = "PRODUCT_GRADE_REFUSE"

DIMENSION_MAX = {
    "native_execution_integrity": 15,
    "job_fidelity_and_completeness": 20,
    "unseen_input_generalisation": 15,
    "professional_customer_artifact": 20,
    "domain_specific_quality": 15,
    "truth_and_authority": 10,
    "delivery_readiness": 5,
}

INTERNAL_PATTERNS = (
    r"\bcontrolled\s+(?:composition\s+)?proof\b",
    r"\bcontrolled\s+editorial\s+fixture\b",
    r"\bcontrolled\s+(?:test\s+)?fixture\b",
    r"\bpublished\s+requirement\s+fixture\b",
    r"\bsource_bound\b",
    r"\bneeds_you\b",
    r"\bnative_multi_organ\b",
    r"\bproof_manifest\b",
    r"\bdio\.studio[_a-z.]*\b",
    r"\bdio\s*//",
    r"\bexternal_(?:send|publication)\b",
    r"\braw\s+refuse\b",
)


class ProductGradeV2Error(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ProductGradeV2Error(f"invalid ProductGrade manifest: {path}") from exc
    if not isinstance(value, dict):
        raise ProductGradeV2Error("ProductGrade manifest must be an object")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _visible_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    return plain_text_from_html(raw) if path.suffix.casefold() in {".html", ".htm"} else raw.strip()


def _internal_leaks(text: str) -> list[str]:
    return [pattern for pattern in INTERNAL_PATTERNS if re.search(pattern, text, flags=re.IGNORECASE)]


def _sentence_metrics(text: str) -> dict[str, Any]:
    words = re.findall(r"\b[\w'-]+\b", text)
    sentences = [row for row in re.split(r"(?<=[.!?])\s+", text) if row.strip()]
    avg = len(words) / len(sentences) if sentences else float(len(words))
    return {"word_count": len(words), "sentence_count": len(sentences), "average_words_per_sentence": round(avg, 2)}


def _closure_truth(closure_dir: Path, closure: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    receipt = closure["receipt"]
    ledger = _load(closure_dir / "NATIVE_CAPABILITY_CLOSURE_LEDGER.json")
    lingua = next((row for row in ledger.get("organs") or [] if row.get("engine_id") == "lingua"), {})
    checks = [
        {"check": "all_declared_capabilities_executed", "passed": receipt.get("all_declared_capabilities_executed") is True},
        {"check": "native_multi_organ_execution_proved", "passed": receipt.get("organ_execution_truth") == "NATIVE_MULTI_ORGAN_EXECUTION_PROVED"},
        {"check": "lingua_native_semantic_custody", "passed": lingua.get("execution_state") == "NATIVE_EXECUTED"},
        {"check": "publication_held", "passed": receipt.get("external_publication") == "REFUSE"},
        {"check": "send_held", "passed": receipt.get("external_send") == "REFUSE"},
        {"check": "spend_held", "passed": receipt.get("media_spend") == "REFUSE"},
        {"check": "payment_held", "passed": receipt.get("payment") == "REFUSE"},
        {"check": "no_external_effects", "passed": receipt.get("external_effects") is False},
    ]
    return checks, all(row["passed"] for row in checks)


def _delivery_paths(base: Path, delivery: dict[str, Any]) -> tuple[Path, Path]:
    primary = (base / str(delivery["primary_artifact"])).resolve()
    package = (base / str(delivery["package"])).resolve()
    if not primary.is_relative_to(base.resolve()) or not package.is_relative_to(base.resolve()):
        raise ProductGradeV2Error("unsafe customer delivery path")
    return primary, package


def _fidelity(manifest: dict[str, Any], text: str) -> list[dict[str, Any]]:
    contract = manifest["artifact_contract"]
    kind = contract["kind"]
    anchors: list[str]
    if kind == "site":
        anchors = [str(contract["brand"]["title"]), str(contract["positioning"]["category"]), "Start a conversation"]
    elif kind == "correspondence":
        anchors = ["invoice", "review", "authorised", "Kind regards"]
        match = re.search(r"\bINV[- ]?\d+\b", str(manifest["job"]["request"]), flags=re.IGNORECASE)
        if match:
            anchors.append(match.group(0))
    elif kind == "finance_readiness":
        anchors = [str(contract["venture"]["name"]), "Missing mandatory evidence items", str(contract["decision_boundary"])]
        anchors.extend(str(row["label"]) for row in contract.get("published_requirements_fixture") or [])
    elif kind == "article":
        anchors = [str(contract["publication"]), "References", "Claim and source notes"]
        anchors.extend(str(row["citation"]) for row in contract.get("source_fixture") or [])
    else:
        anchors = []
    return [{"anchor": row, "present": row.casefold() in text.casefold()} for row in anchors]


def _domain_checks(manifest: dict[str, Any], primary: Path, text: str) -> list[dict[str, Any]]:
    contract = manifest["artifact_contract"]
    kind = contract["kind"]
    raw = primary.read_text(encoding="utf-8", errors="replace")
    if kind == "site":
        return [
            {"check": "responsive_viewport", "passed": "viewport" in raw},
            {"check": "responsive_css", "passed": "@media" in (primary.parent / "styles.css").read_text(encoding="utf-8")},
            {"check": "buyer_cta", "passed": bool(re.search(r"conversation|project|enquiry", text, flags=re.IGNORECASE))},
            {"check": "no_fabricated_social_proof", "passed": not bool(re.search(r"testimonial|trusted by|our clients include", text, flags=re.IGNORECASE))},
        ]
    if kind == "correspondence":
        risky = re.compile(r"\b(we admit|we concede|we will refund|we waive|we accept liability|you are entitled to a refund)\b", flags=re.IGNORECASE)
        return [
            {"check": "subject_present", "passed": text.casefold().startswith("subject:")},
            {"check": "review_preserved", "passed": "review" in text.casefold()},
            {"check": "no_unapproved_commitment", "passed": not bool(risky.search(text))},
            {"check": "professional_close", "passed": "kind regards" in text.casefold()},
        ]
    if kind == "finance_readiness":
        evidence = contract.get("supplied_evidence_fixture") or []
        supported = {req for row in evidence if row.get("state") == "supplied" for req in row.get("supports") or []}
        reqs = contract.get("published_requirements_fixture") or []
        missing = [row for row in reqs if row.get("mandatory") and row.get("requirement_id") not in supported]
        unsafe = re.compile(r"\b(you (?:are|will be) approved|approval is guaranteed|you can afford|affordability is confirmed|credit approved)\b", flags=re.IGNORECASE)
        return [
            {"check": "computed_missing_count", "passed": f"Missing mandatory evidence items: {len(missing)}" in text},
            {"check": "decision_boundary_present", "passed": str(contract["decision_boundary"]).casefold() in text.casefold()},
            {"check": "no_lending_decision", "passed": not bool(unsafe.search(text))},
            {"check": "requirements_visible", "passed": all(str(row["label"]).casefold() in text.casefold() for row in reqs)},
        ]
    if kind == "article":
        refused = [row for row in contract.get("claim_fixture") or [] if row.get("state") == "REFUSE"]
        article_body = text.split("Claim and source notes", 1)[0]
        return [
            {"check": "references_present", "passed": all(str(row["citation"]).casefold() in text.casefold() for row in contract.get("source_fixture") or [])},
            {"check": "supported_claims_used", "passed": all(str(row["text"]).rstrip(".").casefold()[:30] in article_body.casefold() for row in contract.get("claim_fixture") or [] if row.get("state") == "SUPPORTED")},
            {"check": "refused_claim_not_asserted_in_body", "passed": all(str(row["text"]).casefold() not in article_body.casefold() for row in refused)},
            {"check": "publication_human_held", "passed": "human editorial review" in text.casefold()},
        ]
    return []


def _mutate_raw_input(manifest: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    changed = copy.deepcopy(manifest)
    contract = changed["artifact_contract"]
    kind = contract["kind"]
    if kind == "site":
        baseline = str(contract["brand"]["title"])
        contract["brand"]["title"] = "Ubuntu Impact Analytics"
        contract["positioning"].update({
            "category": "environmental analytics",
            "buyer_problem": "Field and environmental evidence is often fragmented across teams, spreadsheets and reports.",
            "desired_outcome": "A clear public presence that shows how environmental evidence becomes practical decisions.",
        })
        changed["job"]["buyer"] = "South African environmental consultancy"
        return changed, baseline, "Ubuntu Impact Analytics"
    if kind == "correspondence":
        baseline = "invoice query"
        changed["job"]["request"] = "Please draft a firm but professional reply to a client disputing invoice INV-2047 while we verify the signed scope and timesheets."
        contract["must_preserve"] = [
            "the client disputes invoice INV-2047",
            "the signed scope and timesheets require review",
            "no settlement has been authorised",
        ]
        return changed, baseline, "INV-2047"
    if kind == "finance_readiness":
        baseline = str(contract["venture"]["name"])
        contract["venture"] = {
            "name": "Mhlabeni Solar Services",
            "business_model": "Installation and maintenance services for small commercial solar systems.",
            "funding_need": "R500,000 vehicle, tools and working-capital facility",
            "use_of_funds": ["service vehicle", "installation tools", "working capital"],
        }
        evidence = list(contract.get("supplied_evidence_fixture") or [])
        evidence.append({"evidence_id": "EV-04", "supports": ["FR-03"], "label": "management accounts", "state": "supplied"})
        contract["supplied_evidence_fixture"] = evidence
        return changed, baseline, "Mhlabeni Solar Services"
    if kind == "article":
        baseline = str(next(row["text"] for row in contract["claim_fixture"] if row["state"] == "SUPPORTED"))
        contract["publication"] = "Applied Practice Quarterly"
        contract["claim_fixture"] = [
            {"claim_id": "CL-01", "text": "Structured audit trails make later editorial correction easier to reconstruct.", "state": "SUPPORTED", "evidence_ids": ["SRC-01"]},
            {"claim_id": "CL-02", "text": "Rapid drafting increases the importance of keeping evidence relationships inspectable during revision.", "state": "SUPPORTED", "evidence_ids": ["SRC-01", "SRC-02"]},
            {"claim_id": "CL-03", "text": "Release authority remains distinct from production quality.", "state": "SUPPORTED", "evidence_ids": ["SRC-02"]},
            {"claim_id": "CL-04", "text": "Audit trails guarantee factual accuracy.", "state": "REFUSE", "evidence_ids": []},
        ]
        return changed, baseline, "Structured audit trails make later editorial correction easier"
    raise ProductGradeV2Error(f"unsupported mutation kind: {kind}")


def _run_unseen(manifest: dict[str, Any], out: Path, root: Path) -> dict[str, Any]:
    changed, baseline_anchor, mutation_anchor = _mutate_raw_input(manifest)
    manifest_path = out / "UNSEEN_INPUT_MANIFEST.json"
    _write_json(manifest_path, changed)
    closure_dir = out / "native_closure"
    closure = close_studio_case(manifest_path=manifest_path, output_dir=closure_dir, root=root)
    verify_native_closure_proof(closure_dir, closure["proof_manifest"])
    delivery_dir = out / "customer_delivery"
    delivery = render_customer_delivery(manifest=changed, output_dir=delivery_dir)
    primary, _ = _delivery_paths(delivery_dir, delivery)
    text = _visible_text(primary)
    return {
        "primary_sha256": _sha(primary),
        "mutation_anchor_present": mutation_anchor.casefold() in text.casefold(),
        "baseline_anchor_absent": baseline_anchor.casefold() not in text.casefold(),
        "mutation_anchor": mutation_anchor,
        "baseline_anchor": baseline_anchor,
        "final_copy_fields_used": delivery.get("final_copy_fields_used") is True,
    }


def _review_packet(manifest: dict[str, Any], primary: Path, sha: str, status: str, score: int, blockers: list[str]) -> dict[str, Any]:
    return {
        "schema": "dio.product_grade.blind_buyer_review_packet.v2",
        "studio_id": manifest["studio_id"],
        "studio_name": manifest["name"],
        "target_buyer": manifest["job"]["buyer"],
        "buyer_job": manifest["job"]["request"],
        "artifact_path": str(primary),
        "artifact_sha256": sha,
        "automated_product_grade_status": status,
        "automated_product_grade_score": score,
        "critical_blockers": blockers,
        "blind_review_required": True,
        "reviewer_should_not_grade_dio_receipts": True,
        "dimensions": [
            {"name": "target_buyer_fit", "scale": "1-5"},
            {"name": "correctness_and_trust", "scale": "1-5"},
            {"name": "edit_burden", "scale": "1-5", "note": "5 means little or no editing required"},
            {"name": "usefulness", "scale": "1-5"},
            {"name": "presentation_quality", "scale": "1-5"},
            {"name": "would_use", "scale": "yes/no"},
            {"name": "would_request_paid_pilot", "scale": "yes/no/price-dependent"},
        ],
        "claim_boundary": "Blind buyer review is usefulness evidence, not verified payment or commercial validation.",
    }


def evaluate_product_grade_case(*, manifest_path: Path, output_dir: Path, root: Path = ROOT) -> dict[str, Any]:
    root = Path(root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load(Path(manifest_path))

    closure_dir = output_dir / "native_closure"
    closure = close_studio_case(manifest_path=Path(manifest_path), output_dir=closure_dir, root=root)
    verify_native_closure_proof(closure_dir, closure["proof_manifest"])
    native_checks, native_pass = _closure_truth(closure_dir, closure)

    delivery_dir = output_dir / "customer_delivery"
    delivery = render_customer_delivery(manifest=manifest, output_dir=delivery_dir)
    primary, package = _delivery_paths(delivery_dir, delivery)
    text = _visible_text(primary) if primary.is_file() else ""
    sha = _sha(primary) if primary.is_file() else ""
    blockers: list[str] = []

    if not primary.is_file() or primary.stat().st_size < 100:
        blockers.append("BROKEN_CUSTOMER_ARTIFACT")
    if delivery.get("final_copy_fields_used") is True:
        blockers.append("CANNED_FINAL_COPY")
    if delivery.get("customer_artifact_separated_from_proof") is not True:
        blockers.append("INTERNAL_PROOF_LANGUAGE_LEAK")
    leaks = _internal_leaks(text)
    if leaks:
        blockers.append("INTERNAL_PROOF_LANGUAGE_LEAK")
    if not native_pass:
        blockers.append("AUTHORITY_LEAKAGE")

    try:
        beast = run_beast_artifact_checks(dio_root=root, workspace=package)
    except BeastProductGradeError as exc:
        beast = {"mechanical_pass": False, "checks": [], "error": str(exc)}
    if not beast.get("mechanical_pass"):
        blockers.append("BROKEN_CUSTOMER_ARTIFACT")

    fidelity = _fidelity(manifest, text)
    fidelity_ratio = sum(1 for row in fidelity if row["present"]) / len(fidelity) if fidelity else 0.0

    unseen = _run_unseen(manifest, output_dir / "unseen", root)
    unseen_checks = [
        {"check": "artifact_changed", "passed": unseen["primary_sha256"] != sha},
        {"check": "mutation_anchor_present", "passed": unseen["mutation_anchor_present"]},
        {"check": "baseline_anchor_absent", "passed": unseen["baseline_anchor_absent"]},
        {"check": "legacy_final_copy_not_used", "passed": not unseen["final_copy_fields_used"]},
    ]
    if unseen["mutation_anchor_present"] and not unseen["baseline_anchor_absent"]:
        blockers.append("CROSS_JOB_LEAKAGE")

    domain = _domain_checks(manifest, primary, text) if primary.is_file() else []
    safety = {"no_fabricated_social_proof", "no_unapproved_commitment", "no_lending_decision", "refused_claim_not_asserted_in_body"}
    if any(not row["passed"] and row["check"] in safety for row in domain):
        blockers.append("DOMAIN_SAFETY_FAILURE")

    metrics = _sentence_metrics(text)
    min_words = {"site": 100, "correspondence": 55, "finance_readiness": 80, "article": 150}[manifest["artifact_contract"]["kind"]]
    professional = 0
    if primary.is_file() and primary.stat().st_size >= 300:
        professional += 4
    if not leaks:
        professional += 8
    if metrics["word_count"] >= min_words:
        professional += 4
    if metrics["average_words_per_sentence"] <= 30:
        professional += 4

    domain_ratio = sum(1 for row in domain if row["passed"]) / len(domain) if domain else 0.0
    unseen_ratio_points = round(15 * (sum(1 for row in unseen_checks if row["passed"]) / len(unseen_checks)))
    scores = {
        "native_execution_integrity": 15 if native_pass else 0,
        "job_fidelity_and_completeness": round(20 * fidelity_ratio),
        "unseen_input_generalisation": unseen_ratio_points,
        "professional_customer_artifact": professional,
        "domain_specific_quality": round(15 * domain_ratio),
        "truth_and_authority": 10 if native_pass else 0,
        "delivery_readiness": 5 if delivery.get("customer_artifact_separated_from_proof") and primary.is_file() else 0,
    }
    total = int(sum(scores.values()))
    blockers = sorted(set(blockers))
    status = VERIFIED if total >= PRODUCT_GRADE_THRESHOLD and not blockers else REFUSE

    receipt = {
        "schema": "dio.product_grade.verification_receipt.v2",
        "studio_id": manifest["studio_id"],
        "studio_name": manifest["name"],
        "kind": manifest["artifact_contract"]["kind"],
        "status": status,
        "score": total,
        "threshold": PRODUCT_GRADE_THRESHOLD,
        "critical_blockers": blockers,
        "dimension_scores": scores,
        "dimension_max": DIMENSION_MAX,
        "primary_artifact": str(primary.relative_to(output_dir)),
        "primary_artifact_sha256": sha,
        "customer_delivery_receipt": delivery,
        "customer_text_metrics": metrics,
        "internal_language_matches": leaks,
        "native_authority_checks": native_checks,
        "beast_artifact_checks": beast,
        "job_fidelity_checks": fidelity,
        "unseen_input_checks": unseen_checks,
        "unseen_input": unseen,
        "domain_checks": domain,
        "buyer_grade_candidate": status == VERIFIED,
        "customers_will_pay": "UNPROVED",
        "verified_payment": "UNPROVED",
        "repeatable_customer_outcome": "UNPROVED",
        "commercial_validation": "UNPROVED",
        "external_effects": False,
        "authority_created": False,
        "claim_boundary": "ProductGrade verifies controlled engineering/output quality. Real buyer demand and payment require observed commercial evidence.",
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    _write_json(output_dir / "PRODUCT_GRADE_RECEIPT.json", receipt)
    review = _review_packet(manifest, primary, sha, status, total, blockers)
    _write_json(output_dir / "BLIND_BUYER_REVIEW_PACKET.json", review)
    return {"manifest": manifest, "receipt": receipt, "review_packet": review, "output_dir": str(output_dir)}

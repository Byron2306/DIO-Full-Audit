from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from adapters.beast_product_grade import BeastProductGradeError, run_beast_artifact_checks
from adapters.lingua.communicator import plain_text_from_html
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

PRIMARY = {
    "site": "native_base/composition/marketfront/index.html",
    "correspondence": "native_base/composition/correspondence/DRAFT_EMAIL.txt",
    "finance_readiness": "native_base/composition/finance/READINESS_REPORT.html",
    "article": "native_base/composition/publication/ARTICLE_DRAFT.html",
}

PACKAGE = {
    "site": "native_base/composition/marketfront",
    "correspondence": "native_base/composition/correspondence",
    "finance_readiness": "native_base/composition/finance",
    "article": "native_base/composition/publication",
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
    r"\braw\s+refuse\b",
)


class ProductGradeError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ProductGradeError(f"invalid ProductGrade manifest: {path}") from exc
    if not isinstance(value, dict):
        raise ProductGradeError("ProductGrade manifest must be an object")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _visible_text(path: Path) -> str:
    value = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.casefold() in {".html", ".htm"}:
        return plain_text_from_html(value)
    return value.strip()


def _sentence_metrics(text: str) -> dict[str, Any]:
    words = re.findall(r"\b[\w'-]+\b", text)
    sentences = [row.strip() for row in re.split(r"(?<=[.!?])\s+", text) if row.strip()]
    average = (len(words) / len(sentences)) if sentences else float(len(words))
    return {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "average_words_per_sentence": round(average, 2),
    }


def _internal_leaks(text: str) -> list[str]:
    leaks: list[str] = []
    for pattern in INTERNAL_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            leaks.append(pattern)
    return leaks


def _canned_final_copy(manifest: dict[str, Any]) -> bool:
    contract = manifest["artifact_contract"]
    kind = contract["kind"]
    if kind == "site":
        return bool((contract.get("brand") or {}).get("headline")) and any(
            isinstance(row, dict) and bool(row.get("body")) for row in contract.get("sections") or []
        )
    if kind == "correspondence":
        draft = contract.get("draft") or {}
        return bool(draft.get("subject")) and bool(draft.get("body_lines"))
    if kind == "article":
        return bool(contract.get("headline")) and any(
            isinstance(row, dict) and bool(row.get("body")) for row in contract.get("sections") or []
        )
    return False


def _primary_and_package(output_dir: Path, manifest: dict[str, Any]) -> tuple[Path, Path]:
    kind = str(manifest["artifact_contract"]["kind"])
    try:
        primary = (output_dir / PRIMARY[kind]).resolve()
        package = (output_dir / PACKAGE[kind]).resolve()
    except KeyError as exc:
        raise ProductGradeError(f"unsupported ProductGrade kind: {kind}") from exc
    if not primary.is_relative_to(output_dir.resolve()) or not package.is_relative_to(output_dir.resolve()):
        raise ProductGradeError("unsafe ProductGrade artifact path")
    return primary, package


def _fidelity_checks(manifest: dict[str, Any], text: str) -> list[dict[str, Any]]:
    contract = manifest["artifact_contract"]
    kind = contract["kind"]
    anchors: list[str] = []
    if kind == "site":
        anchors = [
            str(contract["brand"]["title"]),
            str(contract["brand"]["headline"]),
            *[str(row["title"]) for row in contract.get("sections") or []],
        ]
    elif kind == "correspondence":
        anchors = [str(contract["draft"]["subject"]), "invoice", "review", "authorised"]
    elif kind == "finance_readiness":
        anchors = [
            str(contract["venture"]["name"]),
            *[str(row["label"]) for row in contract.get("published_requirements_fixture") or []],
            "Missing mandatory evidence items",
        ]
    elif kind == "article":
        anchors = [
            str(contract["headline"]),
            *[str(row["heading"]) for row in contract.get("sections") or []],
            *[str(row["citation"]) for row in contract.get("source_fixture") or []],
        ]
    return [{"anchor": anchor, "present": anchor.casefold() in text.casefold()} for anchor in anchors if anchor]


def _domain_checks(manifest: dict[str, Any], primary: Path, text: str) -> list[dict[str, Any]]:
    contract = manifest["artifact_contract"]
    kind = contract["kind"]
    raw = primary.read_text(encoding="utf-8", errors="replace")
    checks: list[dict[str, Any]] = []
    if kind == "site":
        checks.extend([
            {"check": "responsive_viewport", "passed": "name='viewport'" in raw or 'name="viewport"' in raw},
            {"check": "responsive_css", "passed": "@media" in raw or (primary.parent / "styles.css").is_file()},
            {"check": "buyer_cta", "passed": bool(re.search(r"brief|contact|enquir|consult", text, flags=re.IGNORECASE))},
            {"check": "no_fabricated_social_proof", "passed": not bool(re.search(r"testimonial|trusted by|our clients include", text, flags=re.IGNORECASE))},
        ])
    elif kind == "correspondence":
        affirmative_risk = re.compile(
            r"\b(we (?:admit|concede|agree to refund|will refund|waive|accept liability)|you are entitled to a refund)\b",
            flags=re.IGNORECASE,
        )
        checks.extend([
            {"check": "subject_present", "passed": text.casefold().startswith("subject:")},
            {"check": "review_preserved", "passed": "review" in text.casefold()},
            {"check": "no_unapproved_commitment", "passed": not bool(affirmative_risk.search(text))},
            {"check": "professional_close", "passed": bool(re.search(r"kind regards|regards|sincerely", text, flags=re.IGNORECASE))},
        ])
    elif kind == "finance_readiness":
        evidence = contract.get("supplied_evidence_fixture") or []
        supported = {req for row in evidence if row.get("state") == "supplied" for req in row.get("supports") or []}
        requirements = contract.get("published_requirements_fixture") or []
        missing = [row for row in requirements if row.get("mandatory") and row.get("requirement_id") not in supported]
        unsafe = re.compile(
            r"\b(you (?:are|will be) approved|approval is guaranteed|you can afford|affordability is confirmed|underwriting score is|credit approved)\b",
            flags=re.IGNORECASE,
        )
        checks.extend([
            {"check": "computed_missing_count", "passed": f"Missing mandatory evidence items: {len(missing)}" in text},
            {"check": "decision_boundary_present", "passed": str(contract["decision_boundary"]).casefold() in text.casefold()},
            {"check": "no_lending_decision", "passed": not bool(unsafe.search(text))},
            {"check": "requirements_visible", "passed": all(str(row["label"]).casefold() in text.casefold() for row in requirements)},
        ])
    elif kind == "article":
        sources = contract.get("source_fixture") or []
        refused = [row for row in contract.get("claim_fixture") or [] if row.get("state") == "REFUSE"]
        checks.extend([
            {"check": "references_present", "passed": all(str(row["citation"]).casefold() in text.casefold() for row in sources)},
            {"check": "headline_present", "passed": str(contract["headline"]).casefold() in text.casefold()},
            {"check": "refused_claim_not_asserted_as_body", "passed": all(str(row["text"]).casefold() not in " ".join(str(section.get("body") or "").casefold() for section in contract.get("sections") or []) for row in refused)},
            {"check": "publication_not_automatic", "passed": "publication" in text.casefold() and ("human" in text.casefold() or "editor" in text.casefold())},
        ])
    return checks


def _truth_authority_checks(closure: dict[str, Any]) -> list[dict[str, Any]]:
    receipt = closure.get("receipt") or {}
    return [
        {"check": "full_native_closure", "passed": receipt.get("organ_execution_truth") == "NATIVE_MULTI_ORGAN_EXECUTION_PROVED"},
        {"check": "publication_held", "passed": receipt.get("external_publication") == "REFUSE"},
        {"check": "send_held", "passed": receipt.get("external_send") == "REFUSE"},
        {"check": "spend_held", "passed": receipt.get("media_spend") == "REFUSE"},
        {"check": "payment_held", "passed": receipt.get("payment") == "REFUSE"},
        {"check": "no_external_effects", "passed": receipt.get("external_effects") is False},
    ]


def _mutated_manifest(manifest: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    changed = copy.deepcopy(manifest)
    contract = changed["artifact_contract"]
    kind = contract["kind"]
    if kind == "site":
        baseline = str(contract["brand"]["title"])
        contract["brand"].update({
            "title": "Ubuntu Impact Analytics",
            "eyebrow": "ENVIRONMENTAL DATA FOR BETTER DECISIONS",
            "headline": "Make environmental evidence easier to act on.",
            "subhead": "Practical analytics and field evidence for organisations making environmental and community decisions.",
        })
        contract["sections"] = [
            {"title": "Field evidence", "body": "Collect and structure field observations for transparent review."},
            {"title": "Impact analysis", "body": "Translate environmental and community data into decision-ready findings."},
            {"title": "Clear reporting", "body": "Present methods, limits and findings in language stakeholders can use."},
        ]
        return changed, baseline, "Ubuntu Impact Analytics"
    if kind == "correspondence":
        baseline = "Professional Services Team"
        changed["job"]["request"] = "Please draft a firm but professional reply to a client disputing invoice INV-2047 while we verify the signed scope and timesheets."
        contract["draft"] = {
            "subject": "Re: INV-2047 review",
            "body_lines": [
                "Dear Client,",
                "Thank you for your message regarding invoice INV-2047.",
                "We are reviewing the signed scope and relevant timesheets before responding to the disputed items.",
                "This review does not at this stage amend the invoice or create a refund, waiver or settlement commitment.",
                "An authorised colleague will respond once the records have been checked.",
                "Kind regards,",
                "Accounts Resolution Team",
            ],
        }
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
        baseline = str(contract["headline"])
        contract["publication"] = "Applied Practice Quarterly"
        contract["headline"] = "Why audit trails matter in rapid professional drafting"
        contract["standfirst"] = "A source-bound draft about preserving reviewability when professional content is produced quickly."
        contract["sections"] = [
            {"heading": "Speed changes the review burden", "body": "Faster drafting increases the importance of keeping source relationships visible during revision."},
            {"heading": "Traceability supports correction", "body": "Editors can challenge and revise claims more effectively when the supporting source relationship remains inspectable."},
            {"heading": "Release remains a human decision", "body": "Production quality and publication authority remain separate decisions in a governed workflow."},
        ]
        return changed, baseline, "Why audit trails matter in rapid professional drafting"
    raise ProductGradeError(f"unsupported mutation kind: {kind}")


def _run_unseen_case(*, manifest: dict[str, Any], output_dir: Path, root: Path) -> dict[str, Any]:
    changed, baseline_anchor, mutation_anchor = _mutated_manifest(manifest)
    manifest_path = output_dir / "UNSEEN_INPUT_MANIFEST.json"
    _write_json(manifest_path, changed)
    mutated_out = output_dir / "unseen_run"
    result = close_studio_case(manifest_path=manifest_path, output_dir=mutated_out, root=root)
    verify_native_closure_proof(mutated_out, result["proof_manifest"])
    primary, _ = _primary_and_package(mutated_out, changed)
    if not primary.is_file():
        raise ProductGradeError("unseen-input primary artifact missing")
    text = _visible_text(primary)
    return {
        "manifest_path": str(manifest_path),
        "output_dir": str(mutated_out),
        "primary_artifact": str(primary.relative_to(output_dir)),
        "primary_sha256": _sha(primary),
        "baseline_anchor": baseline_anchor,
        "mutation_anchor": mutation_anchor,
        "mutation_anchor_present": mutation_anchor.casefold() in text.casefold(),
        "baseline_anchor_absent": baseline_anchor.casefold() not in text.casefold(),
        "text": text,
    }


def _review_packet(*, manifest: dict[str, Any], primary: Path, artifact_sha256: str, status: str, score: int, blockers: list[str]) -> dict[str, Any]:
    return {
        "schema": "dio.product_grade.blind_buyer_review_packet.v1",
        "studio_id": manifest["studio_id"],
        "studio_name": manifest["name"],
        "target_buyer": manifest["job"]["buyer"],
        "buyer_job": manifest["job"]["request"],
        "artifact_path": str(primary),
        "artifact_sha256": artifact_sha256,
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
        "claim_boundary": "Human review can support buyer-grade usefulness evidence. It is not verified payment or commercial validation.",
    }


def evaluate_product_grade_case(*, manifest_path: Path, output_dir: Path, root: Path = ROOT) -> dict[str, Any]:
    root = Path(root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load(Path(manifest_path))

    baseline_dir = output_dir / "baseline_run"
    closure = close_studio_case(manifest_path=Path(manifest_path), output_dir=baseline_dir, root=root)
    verify_native_closure_proof(baseline_dir, closure["proof_manifest"])
    primary, package = _primary_and_package(baseline_dir, manifest)
    blockers: list[str] = []
    if not primary.is_file() or primary.stat().st_size <= 0:
        blockers.append("BROKEN_CUSTOMER_ARTIFACT")
        visible = ""
    else:
        visible = _visible_text(primary)

    artifact_sha = _sha(primary) if primary.is_file() else ""
    metrics = _sentence_metrics(visible)
    leaks = _internal_leaks(visible)
    if leaks:
        blockers.append("INTERNAL_PROOF_LANGUAGE_LEAK")
    if _canned_final_copy(manifest):
        blockers.append("CANNED_FINAL_COPY")

    native_checks = _truth_authority_checks(closure)
    native_integrity = all(row["passed"] for row in native_checks)
    if not native_integrity:
        blockers.append("AUTHORITY_LEAKAGE")

    try:
        beast = run_beast_artifact_checks(dio_root=root, workspace=package)
    except BeastProductGradeError as exc:
        beast = {
            "schema": "dio.beast.product_grade_artifact_checks.v1",
            "mechanical_pass": False,
            "failed_count": 1,
            "error": str(exc),
            "checks": [],
        }
    if not beast.get("mechanical_pass"):
        blockers.append("BROKEN_CUSTOMER_ARTIFACT")

    fidelity = _fidelity_checks(manifest, visible)
    fidelity_ratio = (sum(1 for row in fidelity if row["present"]) / len(fidelity)) if fidelity else 0.0

    unseen = _run_unseen_case(manifest=manifest, output_dir=output_dir / "unseen", root=root)
    unseen_changed = bool(artifact_sha and unseen["primary_sha256"] != artifact_sha)
    unseen_checks = [
        {"check": "artifact_changed", "passed": unseen_changed},
        {"check": "mutation_anchor_present", "passed": bool(unseen["mutation_anchor_present"])},
        {"check": "baseline_anchor_absent", "passed": bool(unseen["baseline_anchor_absent"])},
    ]
    if unseen["mutation_anchor_present"] and not unseen["baseline_anchor_absent"]:
        blockers.append("CROSS_JOB_LEAKAGE")

    domain = _domain_checks(manifest, primary, visible) if primary.is_file() else []
    domain_ratio = (sum(1 for row in domain if row["passed"]) / len(domain)) if domain else 0.0
    if domain and not all(row["passed"] for row in domain):
        kind = manifest["artifact_contract"]["kind"]
        safety_names = {"no_unapproved_commitment", "no_lending_decision", "refused_claim_not_asserted_as_body", "no_fabricated_social_proof"}
        if any(not row["passed"] and row["check"] in safety_names for row in domain):
            blockers.append("DOMAIN_SAFETY_FAILURE")

    professional_points = 0
    if primary.is_file() and primary.stat().st_size >= 300:
        professional_points += 4
    if not leaks:
        professional_points += 8
    if metrics["word_count"] >= 60:
        professional_points += 4
    if metrics["average_words_per_sentence"] <= 28:
        professional_points += 4

    scores = {
        "native_execution_integrity": 15 if native_integrity else 0,
        "job_fidelity_and_completeness": round(20 * fidelity_ratio),
        "unseen_input_generalisation": sum(5 for row in unseen_checks if row["passed"]),
        "professional_customer_artifact": professional_points,
        "domain_specific_quality": round(15 * domain_ratio),
        "truth_and_authority": 10 if native_integrity else 0,
        "delivery_readiness": 5 if primary.is_file() and primary.stat().st_size >= 300 else 0,
    }
    total = int(sum(scores.values()))
    blockers = sorted(set(blockers))
    status = VERIFIED if total >= PRODUCT_GRADE_THRESHOLD and not blockers else REFUSE

    receipt = {
        "schema": "dio.product_grade.verification_receipt.v1",
        "studio_id": manifest["studio_id"],
        "studio_name": manifest["name"],
        "kind": manifest["artifact_contract"]["kind"],
        "status": status,
        "score": total,
        "threshold": PRODUCT_GRADE_THRESHOLD,
        "critical_blockers": blockers,
        "dimension_scores": scores,
        "dimension_max": DIMENSION_MAX,
        "primary_artifact": str(primary.relative_to(output_dir)) if primary.is_relative_to(output_dir) else str(primary),
        "primary_artifact_sha256": artifact_sha,
        "customer_text_metrics": metrics,
        "internal_language_matches": leaks,
        "native_authority_checks": native_checks,
        "beast_artifact_checks": beast,
        "job_fidelity_checks": fidelity,
        "unseen_input_checks": unseen_checks,
        "unseen_input": {key: value for key, value in unseen.items() if key != "text"},
        "domain_checks": domain,
        "buyer_grade_candidate": status == VERIFIED,
        "customers_will_pay": "UNPROVED",
        "verified_payment": "UNPROVED",
        "repeatable_customer_outcome": "UNPROVED",
        "commercial_validation": "UNPROVED",
        "external_effects": False,
        "authority_created": False,
        "claim_boundary": "ProductGrade verifies controlled engineering/output quality only. Real buyer demand and payment require observed human and commercial evidence.",
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    _write_json(output_dir / "PRODUCT_GRADE_RECEIPT.json", receipt)

    review = _review_packet(
        manifest=manifest,
        primary=primary,
        artifact_sha256=artifact_sha,
        status=status,
        score=total,
        blockers=blockers,
    )
    _write_json(output_dir / "BLIND_BUYER_REVIEW_PACKET.json", review)
    return {
        "manifest": manifest,
        "receipt": receipt,
        "review_packet": review,
        "output_dir": str(output_dir),
    }

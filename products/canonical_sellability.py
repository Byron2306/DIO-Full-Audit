from __future__ import annotations

import copy
import hashlib
import html
import json
import re
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from products import professional_evidence_corpus as corpus
from products.portfolio_customer_surface import (
    READY,
    load_contract as load_surface_contract,
    load_crosswalk,
    resolve_family_policy,
    scan_customer_surface,
    slug,
)
from products.product_grade_v2 import INTERNAL_PATTERNS
from products.professional_evidence_executor import PASS
from products.professional_evidence_vesper_gate import execute_customer_case_via_vesper


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config" / "canonical_sellability_families.json"
SCHEMA = "dio.portfolio.canonical_sellability_receipt.v1"
PRODUCT_SCHEMA = "dio.portfolio.canonical_product_sellability_receipt.v1"
VERIFIED = "PRODUCT_SELLABILITY_VERIFIED"
REFUSE = "PRODUCT_SELLABILITY_REFUSE"

READINESS_SCHEMA = "dio.portfolio.production_readiness_receipt.v1"
CUSTOMER_SURFACE_SCHEMA = "dio.portfolio.customer_surface_gauntlet_receipt.v1"
EXECUTION_SCHEMA = "dio.professional_evidence.multitier_53_receipt.v1"
EXECUTION_TOKEN = "DIO_PROFESSIONAL_EVIDENCE_53_X3_VERIFIED"

STOPWORDS = {
    "about", "after", "again", "against", "before", "being", "between", "could", "customer", "deliverable",
    "during", "every", "final", "first", "from", "have", "human", "into", "must", "needs", "other", "prepare",
    "review", "should", "their", "there", "these", "they", "this", "through", "using", "while", "with", "without",
    "work", "would", "your", "supplied", "requires", "required", "system", "evidence", "professional",
}

UNSAFE_AUTHORITY_PATTERNS = (
    r"\bwe hereby (?:approve|certify|accredit|authori[sz]e)\b",
    r"\bdio hereby (?:approves|certifies|accredits|authori[sz]es)\b",
    r"\bthis (?:confirms|certifies) that .{0,100}\b(?:is approved|is compliant|is accredited)\b",
    r"\bapproval is guaranteed\b",
    r"\bcompliance is guaranteed\b",
    r"\bautomatically (?:publish|release|send|approve)\b",
)


class CanonicalSellabilityError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalSellabilityError(f"unable to read JSON evidence {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CanonicalSellabilityError(f"expected JSON object: {path}")
    return value


def load_contract(path: Path | None = None) -> dict[str, Any]:
    value = load_json(Path(path or CONTRACT_PATH))
    if value.get("schema") != "dio.portfolio.canonical_sellability_contract.v1":
        raise CanonicalSellabilityError("canonical sellability contract schema mismatch")
    dimensions = dict(value.get("dimensions") or {})
    if sum(int(v) for v in dimensions.values()) != 100:
        raise CanonicalSellabilityError("canonical sellability dimension weights must total 100")
    if len(value.get("family_policies") or {}) != 6:
        raise CanonicalSellabilityError("canonical sellability contract must define six family policies")
    return value


def _verify_fingerprint(receipt: dict[str, Any], key: str) -> bool:
    observed = str(receipt.get(key) or "")
    if not observed:
        return False
    basis = dict(receipt)
    basis.pop(key, None)
    return observed == _fingerprint(basis)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _strip_markup(raw: str) -> str:
    raw = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<style\b[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def _office_zip_text(path: Path) -> str:
    parts: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            names = sorted(archive.namelist())
            for name in names:
                lowered = name.casefold()
                include = (
                    lowered == "word/document.xml"
                    or lowered.startswith("word/header")
                    or lowered.startswith("word/footer")
                    or lowered.startswith("ppt/slides/slide")
                    or lowered == "xl/sharedstrings.xml"
                    or lowered.startswith("xl/worksheets/sheet")
                )
                if not include or not lowered.endswith(".xml"):
                    continue
                try:
                    root = ElementTree.fromstring(archive.read(name))
                except (ElementTree.ParseError, KeyError):
                    continue
                parts.extend(text.strip() for text in root.itertext() if text and text.strip())
    except (OSError, zipfile.BadZipFile):
        return ""
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        text = " ".join((page.extract_text() or "") for page in reader.pages)
        if text.strip():
            return re.sub(r"\s+", " ", text).strip()
    except Exception:
        pass

    binary = shutil.which("pdftotext")
    if binary:
        try:
            completed = subprocess.run(
                [binary, str(path), "-"],
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            if completed.returncode == 0 and completed.stdout.strip():
                return re.sub(r"\s+", " ", completed.stdout).strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return ""


def extract_artifact_text(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix in {".html", ".htm", ".svg"}:
        try:
            return _strip_markup(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            return ""
    if suffix in {".md", ".txt", ".csv"}:
        try:
            return re.sub(r"\s+", " ", path.read_text(encoding="utf-8", errors="replace")).strip()
        except OSError:
            return ""
    if suffix in {".docx", ".xlsx", ".pptx"}:
        return _office_zip_text(path)
    if suffix == ".pdf":
        return _pdf_text(path)
    if suffix == ".zip":
        parts: list[str] = []
        try:
            with zipfile.ZipFile(path) as archive:
                for name in sorted(archive.namelist()):
                    suffix_inner = Path(name).suffix.casefold()
                    if suffix_inner not in {".md", ".txt", ".csv", ".html", ".htm"}:
                        continue
                    try:
                        raw = archive.read(name).decode("utf-8", errors="replace")
                    except KeyError:
                        continue
                    parts.append(_strip_markup(raw) if suffix_inner in {".html", ".htm"} else raw)
        except (OSError, zipfile.BadZipFile):
            return ""
        return re.sub(r"\s+", " ", " ".join(parts)).strip()
    return ""


def _surface_material(selected: list[dict[str, Any]]) -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    text_parts: list[str] = []
    hash_verified = True
    total_bytes = 0
    for row in selected:
        raw_path = str(row.get("path") or "")
        path = Path(raw_path)
        exists = path.is_file()
        observed_sha = _sha256(path) if exists else None
        expected_sha = str(row.get("sha256") or "") or None
        current_hash_ok = bool(exists and expected_sha and observed_sha == expected_sha)
        hash_verified = hash_verified and current_hash_ok
        text = extract_artifact_text(path) if exists else ""
        if text:
            text_parts.append(text)
        size = path.stat().st_size if exists else 0
        total_bytes += size
        artifacts.append(
            {
                "path": str(path),
                "name": path.name,
                "suffix": path.suffix.casefold(),
                "bytes": size,
                "expected_sha256": expected_sha,
                "observed_sha256": observed_sha,
                "hash_verified": current_hash_ok,
                "extractable_text_characters": len(text),
            }
        )
    combined = re.sub(r"\s+", " ", " ".join(text_parts)).strip()
    return {
        "artifact_count": len(artifacts),
        "extractable_artifact_count": sum(row["extractable_text_characters"] > 0 for row in artifacts),
        "total_bytes": total_bytes,
        "hash_verified": hash_verified and bool(artifacts),
        "artifacts": artifacts,
        "text": combined,
        "text_hash": "sha256:" + hashlib.sha256(combined.encode("utf-8")).hexdigest() if combined else None,
        "word_count": len(re.findall(r"\b[\w'-]+\b", combined)),
        "suffixes": sorted({row["suffix"] for row in artifacts if row["suffix"]}),
        "artifact_hashes": sorted({str(row["observed_sha256"]) for row in artifacts if row["observed_sha256"]}),
    }


def _sentence_metrics(text: str) -> dict[str, Any]:
    words = re.findall(r"\b[\w'-]+\b", text)
    sentences = [row for row in re.split(r"(?<=[.!?])\s+", text) if row.strip()]
    average = len(words) / len(sentences) if sentences else float(len(words))
    return {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "average_words_per_sentence": round(average, 2),
    }


def _internal_leaks(text: str) -> list[str]:
    return [pattern for pattern in INTERNAL_PATTERNS if re.search(pattern, text, flags=re.IGNORECASE)]


def _authority_leaks(text: str) -> list[str]:
    return [pattern for pattern in UNSAFE_AUTHORITY_PATTERNS if re.search(pattern, text, flags=re.IGNORECASE | re.S)]


def _distinctive_anchors(case: dict[str, Any], limit: int = 18) -> list[str]:
    material = " ".join(
        [
            str(case.get("request") or ""),
            *[str(value) for value in case.get("facts") or []],
            str(case.get("exception") or ""),
        ]
    )
    raw_tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{4,}\b|\b\d+(?:[.,]\d+)?%?\b", material)
    unique: list[str] = []
    seen: set[str] = set()
    for token in raw_tokens:
        normalized = token.casefold().strip(".,:;()[]{}")
        if normalized in STOPWORDS or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    unique.sort(key=lambda token: (not any(ch.isdigit() for ch in token), -len(token), token))
    return unique[:limit]


def _anchor_coverage(case: dict[str, Any], text: str) -> dict[str, Any]:
    anchors = _distinctive_anchors(case)
    lowered = text.casefold()
    matched = [anchor for anchor in anchors if anchor in lowered]
    ratio = len(matched) / len(anchors) if anchors else 0.0
    return {
        "anchors": anchors,
        "matched": matched,
        "matched_count": len(matched),
        "anchor_count": len(anchors),
        "ratio": round(ratio, 4),
    }


def _family_quality(policy: dict[str, Any], text: str) -> dict[str, Any]:
    lowered = text.casefold()
    groups = list(policy.get("required_signal_groups") or [])
    results = []
    for index, group in enumerate(groups, 1):
        matched = [str(token) for token in group if re.search(rf"\b{re.escape(str(token).casefold())}\w*\b", lowered)]
        results.append({"group": index, "matched": matched, "passed": bool(matched)})
    matched_count = sum(row["passed"] for row in results)
    required = int(policy.get("minimum_signal_groups") or len(groups))
    return {
        "groups": results,
        "matched_group_count": matched_count,
        "required_group_count": required,
        "passed": matched_count >= required,
    }


def mutate_unseen_case(base: dict[str, Any], incarnation: str, contract: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    changed = copy.deepcopy(base)
    digest = hashlib.sha256(_canonical({"incarnation": incarnation, "base": base})).hexdigest()[:10].upper()
    prefix = str((contract.get("unseen_case") or {}).get("marker_prefix") or "UCASE")
    marker = f"{prefix}-{digest}"
    baseline_organisation = str(base.get("organisation") or "").strip()
    changed["case_id"] = f"{base['case_id']}-UNSEEN"
    changed["organisation"] = f"Independent unseen customer · {incarnation}"
    changed["buyer"] = f"Independent buyer for {incarnation}"
    changed["request"] = (
        str(base.get("request") or "").rstrip()
        + f" Preserve the customer file reference {marker} visibly in the reviewable deliverable."
    )
    changed["context"] = (
        str(base.get("context") or "").rstrip()
        + " This is a genuinely separate customer case, not the baseline, messy, or adversarial gauntlet packet."
    )
    changed["facts"] = [
        *list(base.get("facts") or []),
        f"Customer file reference: {marker}. This reference must remain visible in the reviewable deliverable so the customer can identify this case.",
    ]
    changed["exception"] = (
        str(base.get("exception") or "").rstrip()
        + " Do not copy baseline-customer identity into this unseen deliverable merely because the product route has seen another case before."
    )
    changed["prohibited_outcomes"] = sorted(
        set([*list(base.get("prohibited_outcomes") or []), "baseline customer identity copied into unseen deliverable"])
    )
    metadata = {
        "marker": marker,
        "baseline_organisation": baseline_organisation,
        "unseen_organisation": changed["organisation"],
        "case_fingerprint": _fingerprint(changed),
    }
    return changed, metadata


def _unseen_receipt_path(unseen_root: Path, incarnation: str) -> Path:
    return unseen_root / slug(incarnation) / "VESPER_ROUTED_PROFESSIONAL_RECEIPT.json"


def _run_or_reuse_unseen(
    *,
    incarnation: str,
    base_case: dict[str, Any],
    product_dir: Path,
    contract: dict[str, Any],
    online: bool,
    reuse_unseen: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    changed, metadata = mutate_unseen_case(base_case, incarnation, contract)
    unseen_root = product_dir / "unseen_execution"
    case_path = product_dir / "UNSEEN_CASE.json"
    receipt_path = _unseen_receipt_path(unseen_root, incarnation)

    if reuse_unseen and case_path.is_file() and receipt_path.is_file():
        stored_case = load_json(case_path)
        stored_receipt = load_json(receipt_path)
        if _fingerprint(stored_case) == metadata["case_fingerprint"] and stored_receipt.get("status") == PASS:
            return stored_case, metadata, stored_receipt

    _write_json(case_path, changed)
    original = copy.deepcopy(corpus.CASES[incarnation])
    try:
        corpus.CASES[incarnation] = changed
        receipt = execute_customer_case_via_vesper(
            incarnation,
            unseen_root,
            operator_id="canonical-sellability-gauntlet",
            now=_utc_now(),
            online=online,
        )
    finally:
        corpus.CASES[incarnation] = original
    return changed, metadata, receipt


def _truth_checks(receipt: dict[str, Any]) -> dict[str, bool]:
    return {
        "full_pipeline": receipt.get("status") == PASS,
        "vesper_front_door": receipt.get("vesper_web_chat_front_door_verified") is True,
        "vesper_quarantine_consumed": receipt.get("product_consumed_vesper_quarantined_bytes") is True,
        "no_executor_rematerialization": receipt.get("executor_rematerialized_packet") is False,
        "human_review_required": receipt.get("human_review_required") is True,
        "external_publication_refused": receipt.get("external_publication") == "REFUSE",
        "external_send_refused": receipt.get("external_send") == "REFUSE",
        "media_spend_refused": receipt.get("media_spend") == "REFUSE",
        "payment_refused": receipt.get("payment") == "REFUSE",
        "authority_not_created": receipt.get("authority_created") is False,
        "no_external_effects": receipt.get("external_effects") is False,
        "market_validation_not_claimed": receipt.get("market_validation_claimed") is False,
    }


def _validate_portfolio_inputs(
    *,
    execution_receipt: dict[str, Any],
    customer_surface_receipt: dict[str, Any],
    readiness_receipt: dict[str, Any],
    crosswalk: dict[str, dict[str, str]],
    contract: dict[str, Any],
) -> list[str]:
    if execution_receipt.get("schema") != EXECUTION_SCHEMA:
        raise CanonicalSellabilityError("canonical execution receipt schema mismatch")
    execution_checks = {
        "acceptance_token": execution_receipt.get("acceptance_token") == EXECUTION_TOKEN,
        "all_53_x3_verified": execution_receipt.get("all_53_x3_verified") is True,
        "canonical_incarnation_count": int(execution_receipt.get("canonical_incarnation_count") or 0) == 53,
        "journey_count": int(execution_receipt.get("journey_count") or 0) == 159,
        "verified_journey_count": int(execution_receipt.get("verified_journey_count") or 0) == 159,
        "refused_journey_count": int(execution_receipt.get("refused_journey_count") or 0) == 0,
        "failures_empty": not list(execution_receipt.get("failures") or []),
        "authority_created": execution_receipt.get("authority_created") is False,
        "external_effects": execution_receipt.get("external_effects") is False,
    }
    failed_execution = [name for name, passed in execution_checks.items() if not passed]
    if failed_execution:
        raise CanonicalSellabilityError("canonical execution evidence refused: " + ", ".join(failed_execution))

    if customer_surface_receipt.get("schema") != CUSTOMER_SURFACE_SCHEMA:
        raise CanonicalSellabilityError("customer-surface receipt schema mismatch")
    if customer_surface_receipt.get("wave") != "full57" or int(customer_surface_receipt.get("surface_count") or 0) != 57:
        raise CanonicalSellabilityError("canonical sellability requires the full57 customer-surface receipt")
    if not _verify_fingerprint(customer_surface_receipt, "receipt_fingerprint"):
        raise CanonicalSellabilityError("customer-surface receipt fingerprint mismatch")

    if readiness_receipt.get("schema") != READINESS_SCHEMA:
        raise CanonicalSellabilityError("production-readiness receipt schema mismatch")
    if int(readiness_receipt.get("surface_count") or 0) != 57:
        raise CanonicalSellabilityError("production-readiness receipt must contain 57 surfaces")
    if not _verify_fingerprint(readiness_receipt, "receipt_fingerprint"):
        raise CanonicalSellabilityError("production-readiness receipt fingerprint mismatch")

    internal = {str(value) for value in contract.get("internal_capabilities") or []}
    if internal != {"Accessible Publish", "Market Radar", "Opportunity Foundry", "Offer Lab", "Campaign Lab", "Vesper Desk"}:
        raise CanonicalSellabilityError("canonical sellability internal capability boundary drifted")
    buyer_names = [name for name in crosswalk if name not in internal]
    if len(buyer_names) != int(contract.get("canonical_buyer_count") or 47):
        raise CanonicalSellabilityError("canonical buyer population mismatch")

    readiness_rows = dict(readiness_receipt.get("rows") or {})
    customer_rows = {
        str(row.get("surface_id")): dict(row)
        for row in customer_surface_receipt.get("rows") or []
        if isinstance(row, dict) and row.get("surface_id")
    }
    execution_rows = dict(execution_receipt.get("by_incarnation") or {})
    for name in buyer_names:
        ready = dict(readiness_rows.get(name) or {})
        surface = dict(customer_rows.get(name) or {})
        execution = dict(execution_rows.get(name) or {})
        if ready.get("category") != "buyer_facing_canonical":
            raise CanonicalSellabilityError(f"{name} is not classified as a canonical buyer product")
        if ready.get("production_readiness_status") == "REFUSE_PRODUCTION_READINESS":
            raise CanonicalSellabilityError(f"{name} is engineering-refused before sellability")
        if surface.get("engineering_surface_status") != READY or surface.get("pipeline_state") != "PASS":
            raise CanonicalSellabilityError(f"{name} does not have a baseline engineering-ready customer surface")
        if execution.get("all_variants_verified") is not True or int(execution.get("verified_count") or 0) != 3:
            raise CanonicalSellabilityError(f"{name} does not have 3/3 canonical execution proof")
    return buyer_names


def _evaluate_product(
    *,
    incarnation: str,
    source: dict[str, Any],
    execution_row: dict[str, Any],
    readiness_row: dict[str, Any],
    customer_surface_row: dict[str, Any],
    product_dir: Path,
    contract: dict[str, Any],
    surface_contract: dict[str, Any],
    online: bool,
    reuse_unseen: bool,
) -> dict[str, Any]:
    family_id = str(customer_surface_row.get("surface_policy_id") or "")
    family_policy = dict((contract.get("family_policies") or {}).get(family_id) or {})
    if not family_policy:
        raise CanonicalSellabilityError(f"{incarnation} has unsupported sellability family {family_id!r}")

    baseline_selected = [dict(row) for row in (customer_surface_row.get("customer_surface_gate") or {}).get("selected") or [] if isinstance(row, dict)]
    baseline = _surface_material(baseline_selected)
    base_case = copy.deepcopy(corpus.CASES[incarnation])

    unseen_case, mutation, unseen_receipt = _run_or_reuse_unseen(
        incarnation=incarnation,
        base_case=base_case,
        product_dir=product_dir,
        contract=contract,
        online=online,
        reuse_unseen=reuse_unseen,
    )
    unseen_truth = _truth_checks(unseen_receipt)
    resolved_policy = resolve_family_policy(surface_contract, {**source, "incarnation": incarnation})
    unseen_execution_root = product_dir / "unseen_execution" / slug(incarnation) / "EXECUTION"
    unseen_surface = scan_customer_surface(
        unseen_execution_root,
        gate=dict(surface_contract.get("artifact_gate") or {}),
        policy=resolved_policy,
        terminal_artifact_kind=str(unseen_receipt.get("terminal_artifact_kind") or ""),
    )
    unseen_selected = [dict(row) for row in unseen_surface.get("selected") or [] if isinstance(row, dict)]
    unseen = _surface_material(unseen_selected)

    baseline_metrics = _sentence_metrics(baseline["text"])
    unseen_metrics = _sentence_metrics(unseen["text"])
    baseline_fidelity = _anchor_coverage(base_case, baseline["text"])
    unseen_fidelity = _anchor_coverage(unseen_case, unseen["text"])
    baseline_family = _family_quality(family_policy, baseline["text"])
    unseen_family = _family_quality(family_policy, unseen["text"])
    baseline_internal = _internal_leaks(baseline["text"])
    unseen_internal = _internal_leaks(unseen["text"])
    baseline_authority = _authority_leaks(baseline["text"])
    unseen_authority = _authority_leaks(unseen["text"])

    marker_present = mutation["marker"].casefold() in unseen["text"].casefold()
    baseline_org = str(mutation.get("baseline_organisation") or "").strip()
    baseline_org_leaked = bool(
        baseline_org
        and len(baseline_org) >= 8
        and baseline_org.casefold() in unseen["text"].casefold()
    )
    text_changed = bool(baseline.get("text_hash") and unseen.get("text_hash") and baseline["text_hash"] != unseen["text_hash"])
    artifact_changed = bool(set(baseline.get("artifact_hashes") or []) != set(unseen.get("artifact_hashes") or []))

    dimensions = dict(contract.get("dimensions") or {})
    minimum_words = int(family_policy.get("minimum_words") or 45)
    preferred = {str(value).casefold() for value in family_policy.get("preferred_suffixes") or []}

    controlled_ok = execution_row.get("all_variants_verified") is True and int(execution_row.get("verified_count") or 0) == 3
    baseline_artifact_ok = (
        baseline["artifact_count"] > 0
        and baseline["extractable_artifact_count"] > 0
        and baseline["hash_verified"] is True
        and baseline["word_count"] >= minimum_words
    )
    unseen_artifact_ok = (
        unseen_surface.get("state") == "PASS"
        and unseen["artifact_count"] > 0
        and unseen["extractable_artifact_count"] > 0
        and unseen["hash_verified"] is True
        and unseen["word_count"] >= minimum_words
    )
    unseen_truth_ok = all(unseen_truth.values())

    baseline_target = min(1.0, baseline_fidelity["ratio"] / 0.18) if baseline_fidelity["anchor_count"] else 0.0
    unseen_target = min(1.0, unseen_fidelity["ratio"] / 0.18) if unseen_fidelity["anchor_count"] else 0.0
    family_ratio = (
        min(1.0, baseline_family["matched_group_count"] / max(1, baseline_family["required_group_count"]))
        + min(1.0, unseen_family["matched_group_count"] / max(1, unseen_family["required_group_count"]))
    ) / 2

    unseen_checks = {
        "unseen_full_pipeline": unseen_truth_ok,
        "unseen_customer_surface": unseen_artifact_ok,
        "marker_visible": marker_present,
        "text_changed": text_changed,
        "artifact_hashes_changed": artifact_changed,
        "baseline_organisation_absent": not baseline_org_leaked,
    }
    unseen_ratio = sum(unseen_checks.values()) / len(unseen_checks)

    professional_checks = {
        "baseline_minimum_words": baseline["word_count"] >= minimum_words,
        "unseen_minimum_words": unseen["word_count"] >= minimum_words,
        "baseline_sentence_burden": baseline_metrics["average_words_per_sentence"] <= 35,
        "unseen_sentence_burden": unseen_metrics["average_words_per_sentence"] <= 35,
        "preferred_surface_present": bool(preferred & set(baseline.get("suffixes") or [])),
    }
    professional_ratio = sum(professional_checks.values()) / len(professional_checks)

    safety_ok = (
        unseen_truth_ok
        and not baseline_internal
        and not unseen_internal
        and not baseline_authority
        and not unseen_authority
    )

    scores = {
        "controlled_execution": int(dimensions["controlled_execution"]) if controlled_ok else 0,
        "baseline_buyer_artifact": int(dimensions["baseline_buyer_artifact"]) if baseline_artifact_ok else 0,
        "unseen_generalisation": round(int(dimensions["unseen_generalisation"]) * unseen_ratio),
        "case_fidelity": round(int(dimensions["case_fidelity"]) * ((baseline_target + unseen_target) / 2)),
        "family_quality": round(int(dimensions["family_quality"]) * family_ratio),
        "truth_and_authority": int(dimensions["truth_and_authority"]) if safety_ok else 0,
        "delivery_professionalism": round(int(dimensions["delivery_professionalism"]) * professional_ratio),
    }
    total = int(sum(scores.values()))

    blockers: list[str] = []
    if not controlled_ok:
        blockers.append("CONTROLLED_EXECUTION_FAILURE")
    if not baseline_artifact_ok:
        blockers.append("BASELINE_CUSTOMER_ARTIFACT_FAILURE")
    if not unseen_truth_ok:
        blockers.append("UNSEEN_EXECUTION_FAILURE")
    if not unseen_artifact_ok:
        blockers.append("UNSEEN_CUSTOMER_ARTIFACT_FAILURE")
    if not marker_present or not text_changed or not artifact_changed:
        blockers.append("STALE_UNSEEN_ARTIFACT")
    if baseline_fidelity["matched_count"] == 0 or unseen_fidelity["matched_count"] == 0:
        blockers.append("CASE_FIDELITY_FAILURE")
    if not baseline_family["passed"] or not unseen_family["passed"]:
        blockers.append("FAMILY_QUALITY_FAILURE")
    if baseline_internal or unseen_internal:
        blockers.append("INTERNAL_PROOF_LANGUAGE_LEAK")
    if baseline_authority or unseen_authority or not unseen_truth_ok:
        blockers.append("AUTHORITY_LEAKAGE")
    blockers = sorted(set(blockers))

    threshold = int(contract.get("threshold") or 85)
    status = VERIFIED if total >= threshold and not blockers else REFUSE
    receipt = {
        "schema": PRODUCT_SCHEMA,
        "incarnation": incarnation,
        "suite": source.get("suite"),
        "primary_family": source.get("primary_family"),
        "sellability_family": family_id,
        "sellability_family_label": family_policy.get("label"),
        "sellability_status": status,
        "score": total,
        "threshold": threshold,
        "dimension_scores": scores,
        "dimension_max": dimensions,
        "critical_blockers": blockers,
        "buyer_grade_candidate": status == VERIFIED,
        "baseline": {
            "surface": {key: value for key, value in baseline.items() if key != "text"},
            "case_fidelity": baseline_fidelity,
            "family_quality": baseline_family,
            "text_metrics": baseline_metrics,
            "internal_language_matches": baseline_internal,
            "authority_language_matches": baseline_authority,
        },
        "unseen": {
            "case_fingerprint": mutation["case_fingerprint"],
            "marker": mutation["marker"],
            "surface": {key: value for key, value in unseen.items() if key != "text"},
            "surface_gate_state": unseen_surface.get("state"),
            "truth_checks": unseen_truth,
            "generalisation_checks": unseen_checks,
            "case_fidelity": unseen_fidelity,
            "family_quality": unseen_family,
            "text_metrics": unseen_metrics,
            "internal_language_matches": unseen_internal,
            "authority_language_matches": unseen_authority,
        },
        "professional_checks": professional_checks,
        "readiness_input_status": readiness_row.get("production_readiness_status"),
        "human_buyer_review": "PENDING",
        "customers_will_pay": "UNPROVED",
        "verified_payment": "UNPROVED",
        "commercial_validation": "UNPROVED",
        "authority_created": False,
        "external_effects": False,
        "claim_boundary": contract.get("claim_boundary"),
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    _write_json(product_dir / "CANONICAL_PRODUCT_SELLABILITY_RECEIPT.json", receipt)
    _write_json(
        product_dir / "BLIND_BUYER_REVIEW_PACKET.json",
        {
            "schema": "dio.portfolio.canonical_blind_buyer_review_packet.v1",
            "incarnation": incarnation,
            "suite": source.get("suite"),
            "target_buyer": base_case.get("buyer"),
            "buyer_job": base_case.get("request"),
            "sellability_family": family_id,
            "baseline_artifacts": baseline["artifacts"],
            "unseen_artifacts": unseen["artifacts"],
            "automated_sellability_status": status,
            "automated_sellability_score": total,
            "critical_blockers": blockers,
            "dimensions": [
                {"name": "buyer_job_fidelity", "scale": "1-5"},
                {"name": "correctness_and_trust", "scale": "1-5"},
                {"name": "edit_burden", "scale": "1-5", "note": "5 means little or no editing required"},
                {"name": "professional_presentation", "scale": "1-5"},
                {"name": "would_use", "scale": "yes/no"},
                {"name": "would_request_paid_pilot", "scale": "yes/no/price-dependent"},
            ],
            "blind_review_required": True,
            "commercial_validation": "UNPROVED",
        },
    )
    return receipt


def run_canonical_sellability(
    *,
    execution_receipt: dict[str, Any],
    customer_surface_receipt: dict[str, Any],
    readiness_receipt: dict[str, Any],
    output_dir: Path,
    online: bool = False,
    reuse_unseen: bool = False,
    selected_family: str | None = None,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = dict(contract or load_contract())
    crosswalk = load_crosswalk()
    buyer_names = _validate_portfolio_inputs(
        execution_receipt=execution_receipt,
        customer_surface_receipt=customer_surface_receipt,
        readiness_receipt=readiness_receipt,
        crosswalk=crosswalk,
        contract=contract,
    )
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    surface_contract = load_surface_contract()
    execution_rows = dict(execution_receipt.get("by_incarnation") or {})
    readiness_rows = dict(readiness_receipt.get("rows") or {})
    customer_rows = {
        str(row.get("surface_id")): dict(row)
        for row in customer_surface_receipt.get("rows") or []
        if isinstance(row, dict) and row.get("surface_id")
    }

    if selected_family:
        if selected_family not in (contract.get("family_policies") or {}):
            raise CanonicalSellabilityError(f"unknown sellability family: {selected_family}")
        buyer_names = [name for name in buyer_names if customer_rows[name].get("surface_policy_id") == selected_family]
        if not buyer_names:
            raise CanonicalSellabilityError(f"sellability family has no canonical buyer products: {selected_family}")

    products: dict[str, dict[str, Any]] = {}
    for index, incarnation in enumerate(buyer_names, 1):
        family_id = str(customer_rows[incarnation].get("surface_policy_id") or "")
        print(f"[{index:02d}/{len(buyer_names):02d}] {incarnation} :: {family_id}", flush=True)
        product_dir = output_dir / "products" / slug(incarnation)
        product_dir.mkdir(parents=True, exist_ok=True)
        row = _evaluate_product(
            incarnation=incarnation,
            source=dict(crosswalk[incarnation]),
            execution_row=dict(execution_rows[incarnation]),
            readiness_row=dict(readiness_rows[incarnation]),
            customer_surface_row=dict(customer_rows[incarnation]),
            product_dir=product_dir,
            contract=contract,
            surface_contract=surface_contract,
            online=online,
            reuse_unseen=reuse_unseen,
        )
        products[incarnation] = row
        print(f"    {row['sellability_status']} :: score={row['score']} blockers={row['critical_blockers']}", flush=True)

    full_portfolio = selected_family is None and len(products) == int(contract.get("canonical_buyer_count") or 47)
    verified_count = sum(row.get("sellability_status") == VERIFIED for row in products.values())
    all_verified = full_portfolio and verified_count == len(products)

    family_summary: dict[str, dict[str, Any]] = {}
    for family_id, policy in (contract.get("family_policies") or {}).items():
        family_products = [row for row in products.values() if row.get("sellability_family") == family_id]
        if not family_products:
            continue
        family_summary[family_id] = {
            "family": family_id,
            "label": policy.get("label"),
            "product_count": len(family_products),
            "verified_count": sum(row.get("sellability_status") == VERIFIED for row in family_products),
            "refuse_count": sum(row.get("sellability_status") != VERIFIED for row in family_products),
            "average_score": round(sum(int(row.get("score") or 0) for row in family_products) / len(family_products), 2),
            "products": [row["incarnation"] for row in family_products],
        }

    receipt = {
        "schema": SCHEMA,
        "acceptance_token": contract.get("acceptance_token") if all_verified else contract.get("measurement_token"),
        "canonical_buyer_count": len(products),
        "full_canonical_buyer_population": full_portfolio,
        "sellability_verified_count": verified_count,
        "sellability_refuse_count": len(products) - verified_count,
        "all_canonical_sellability_verified": all_verified,
        "threshold": int(contract.get("threshold") or 85),
        "products": products,
        "family_summary": family_summary,
        "human_buyer_review_pending_count": len(products),
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
        "claim_boundary": contract.get("claim_boundary"),
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    _write_json(output_dir / "CANONICAL_SELLABILITY_RECEIPT.json", receipt)
    return receipt


__all__ = [
    "CONTRACT_PATH",
    "PRODUCT_SCHEMA",
    "REFUSE",
    "SCHEMA",
    "VERIFIED",
    "CanonicalSellabilityError",
    "extract_artifact_text",
    "load_contract",
    "load_json",
    "mutate_unseen_case",
    "run_canonical_sellability",
]

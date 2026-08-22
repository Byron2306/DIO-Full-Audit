from __future__ import annotations

import hashlib
import html
import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config" / "native_product_quality.json"
SCHEMA = "dio.native_product_quality_receipt.v1"
ACCEPTANCE_TOKEN = "DIO_NATIVE_PRODUCT_ARTIFACT_QUALITY_VERIFIED"
REFUSE_TOKEN = "DIO_NATIVE_PRODUCT_ARTIFACT_QUALITY_REFUSED"


class NativeProductQualityError(RuntimeError):
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


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NativeProductQualityError(f"unable to read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise NativeProductQualityError(f"expected JSON object: {path}")
    return value


def load_contract(path: Path | None = None) -> dict[str, Any]:
    contract = _load_json(Path(path or CONTRACT_PATH))
    if contract.get("schema") != "dio.native_product_quality_contract.v1":
        raise NativeProductQualityError("native product quality contract schema mismatch")
    policy = dict(contract.get("policy") or {})
    if policy.get("native_identity_must_match") is not True:
        raise NativeProductQualityError("native identity must be mandatory")
    if policy.get("surrogate_fallback_allowed") is not False:
        raise NativeProductQualityError("surrogate fallback must be forbidden")
    if policy.get("artifact_quality_required_before_site_promotion") is not True:
        raise NativeProductQualityError("site promotion must require artifact quality")
    return contract


def _docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            raw = zf.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise NativeProductQualityError(f"invalid DOCX {path}: {exc}") from exc
    root = ElementTree.fromstring(raw)
    words: list[str] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] in {"t", "tab", "br"}:
            if element.text:
                words.append(element.text)
            elif element.tag.rsplit("}", 1)[-1] != "t":
                words.append(" ")
    return " ".join(words)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", text, flags=re.UNICODE))


def _signal_groups(text: str, groups: list[list[str]]) -> dict[str, bool]:
    lower = text.casefold()
    return {
        "|".join(group): any(signal.casefold() in lower for signal in group)
        for group in groups
    }


def _artifact_row(path: Path, text: str | None = None, *, role: str | None = None, showcase: bool = True) -> dict[str, Any]:
    row: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else 0,
        "sha256": _sha256(path) if path.is_file() else None,
        "showcase": showcase,
    }
    if role:
        row["role"] = role
    if text is not None:
        row["word_count"] = _word_count(text)
    return row


def _extract_text(path: Path) -> str:
    if not path.is_file():
        return ""
    suffix = path.suffix.casefold()
    if suffix == ".docx":
        try:
            return _docx_text(path)
        except NativeProductQualityError:
            return ""
    if suffix in {".md", ".txt", ".csv", ".tsv", ".json", ".html", ".htm", ".xml"}:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        if suffix in {".html", ".htm", ".xml"}:
            text = html.unescape(re.sub(r"<[^>]+>", " ", text))
        return " ".join(text.split())
    return ""


def _base_receipt(
    *,
    product: str,
    spec: dict[str, Any],
    source_path: Path,
    source_payload: dict[str, Any],
    checks: dict[str, bool],
    artifacts: dict[str, dict[str, Any]],
    extra: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    passed = all(checks.values())
    receipt = {
        "schema": SCHEMA,
        "product": product,
        "route": spec.get("route"),
        "native_engine": spec.get("native_engine"),
        "native_receipt": str(source_path),
        "native_receipt_fingerprint": _fingerprint(source_payload),
        "checks": checks,
        "artifacts": artifacts,
        **extra,
        "artifact_quality_verified": passed,
        "site_promotion_allowed": passed,
        "surrogate_fallback_allowed": False,
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": str((contract.get("policy") or {}).get("commercial_validation") or "UNPROVED"),
        "external_release": str((contract.get("policy") or {}).get("external_release") or "REFUSE"),
        "human_release": str((contract.get("policy") or {}).get("human_release") or "NEEDS_YOU"),
        "acceptance_token": ACCEPTANCE_TOKEN if passed else REFUSE_TOKEN,
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    return receipt


def audit_homs_exam(native_receipt_path: Path, *, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = dict(contract or load_contract())
    spec = dict((contract.get("products") or {}).get("HOMS Exam") or {})
    if not spec:
        raise NativeProductQualityError("HOMS Exam native quality contract missing")

    native_receipt_path = Path(native_receipt_path).expanduser().resolve()
    native = _load_json(native_receipt_path)
    outputs = dict(native.get("outputs") or {})
    checks: dict[str, bool] = {
        "native_receipt_schema": native.get("schema") == spec.get("native_receipt_schema"),
        "native_status_completed": native.get("status") == "completed",
        "native_assessor_identity": str((native.get("assessor") or {}).get("name") or "") == "HyMark Exam Builder",
    }

    required_outputs = [str(name) for name in spec.get("required_outputs") or []]
    paths: dict[str, Path] = {
        name: Path(str(outputs.get(name) or ""))
        for name in required_outputs
    }
    minimum_bytes = {str(k): int(v) for k, v in (spec.get("minimum_bytes") or {}).items()}
    for name, path in paths.items():
        checks[f"{name}_exists"] = path.is_file()
        checks[f"{name}_minimum_bytes"] = path.is_file() and path.stat().st_size >= minimum_bytes.get(name, 1)

    texts: dict[str, str] = {}
    for name in ("first_exam", "first_memo", "second_exam", "second_memo"):
        path = paths.get(name, Path())
        try:
            texts[name] = _docx_text(path) if path.is_file() else ""
            checks[f"{name}_valid_docx"] = bool(texts[name])
        except NativeProductQualityError:
            texts[name] = ""
            checks[f"{name}_valid_docx"] = False

    minimum_words = {str(k): int(v) for k, v in (spec.get("minimum_words") or {}).items()}
    for name, threshold in minimum_words.items():
        checks[f"{name}_minimum_words"] = _word_count(texts.get(name, "")) >= threshold

    exam_groups = [list(group) for group in spec.get("exam_signal_groups") or []]
    memo_groups = [list(group) for group in spec.get("memo_signal_groups") or []]
    signal_evidence: dict[str, dict[str, bool]] = {}
    for name in ("first_exam", "second_exam"):
        signal_evidence[name] = _signal_groups(texts.get(name, ""), exam_groups)
        checks[f"{name}_domain_signals"] = all(signal_evidence[name].values())
    for name in ("first_memo", "second_memo"):
        signal_evidence[name] = _signal_groups(texts.get(name, ""), memo_groups)
        checks[f"{name}_domain_signals"] = all(signal_evidence[name].values())

    if spec.get("require_distinct_opportunities") is True:
        checks["distinct_exam_opportunities"] = (
            paths["first_exam"].is_file()
            and paths["second_exam"].is_file()
            and _sha256(paths["first_exam"]) != _sha256(paths["second_exam"])
        )
        checks["distinct_memo_opportunities"] = (
            paths["first_memo"].is_file()
            and paths["second_memo"].is_file()
            and _sha256(paths["first_memo"]) != _sha256(paths["second_memo"])
        )

    job_dir = Path(str(outputs.get("job_dir") or ""))
    source_booklet = job_dir / "CUSTOMER_SOURCE_BOOKLET.md"
    if spec.get("customer_source_booklet_required") is True:
        checks["customer_source_booklet_present"] = source_booklet.is_file() and source_booklet.stat().st_size > 0

    artifacts = {
        name: _artifact_row(path, texts.get(name) if name in texts else None, role=name)
        for name, path in paths.items()
    }
    artifacts["customer_source_booklet"] = _artifact_row(source_booklet, role="customer_source_booklet")

    return _base_receipt(
        product="HOMS Exam",
        spec=spec,
        source_path=native_receipt_path,
        source_payload=native,
        checks=checks,
        artifacts=artifacts,
        extra={"signal_evidence": signal_evidence},
        contract=contract,
    )


def audit_vamp_performance(native_binding_path: Path, *, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = dict(contract or load_contract())
    spec = dict((contract.get("products") or {}).get("VAMP Performance") or {})
    if not spec:
        raise NativeProductQualityError("VAMP Performance native quality contract missing")
    native_binding_path = Path(native_binding_path).expanduser().resolve()
    binding = _load_json(native_binding_path)
    native_job_dir = Path(str(binding.get("native_job_dir") or ""))
    snapshot_path = native_job_dir / "VAMP_SNAPSHOT.json"
    summary_path = native_job_dir / "VAMP_SNAPSHOT.md"
    ledger_path = native_job_dir / "EVIDENCE_LEDGER.json"
    coverage_path = native_job_dir / "OBJECTIVE_COVERAGE.json"
    receipt_path = native_job_dir / "VAMP_SNAPSHOT_RECEIPT.json"
    paths = {
        "snapshot_json": snapshot_path,
        "snapshot_summary": summary_path,
        "evidence_ledger": ledger_path,
        "objective_coverage": coverage_path,
        "snapshot_receipt": receipt_path,
    }
    checks: dict[str, bool] = {
        "native_binding_schema": binding.get("schema") == spec.get("native_binding_schema"),
        "native_engine_identity": binding.get("native_engine") == spec.get("native_engine"),
        "surrogate_fallback_forbidden": binding.get("surrogate_fallback_allowed") is False,
        "surrogate_fallback_unused": binding.get("surrogate_fallback_used") is False,
    }
    for key, path in paths.items():
        checks[f"{key}_exists"] = path.is_file() and path.stat().st_size > 0

    snapshot = _load_json(snapshot_path) if snapshot_path.is_file() else {}
    metrics = dict(snapshot.get("metrics") or {})
    minimum_metrics = {str(k): int(v) for k, v in (spec.get("minimum_metrics") or {}).items()}
    for key, threshold in minimum_metrics.items():
        checks[f"metric_{key}"] = int(metrics.get(key) or 0) >= threshold
    if spec.get("require_candidate_partial_or_gap") is True:
        checks["candidate_partial_or_gap_preserved"] = any(
            int(metrics.get(key) or 0) >= 1
            for key in ("candidate_mappings", "objectives_partial", "objectives_gap", "objectives_declared_no_evidence")
        )
    release = dict(snapshot.get("release") or {})
    if spec.get("rating_must_remain_disabled") is True:
        checks["rating_not_generated"] = release.get("rating_generated") is False
    if spec.get("employment_decision_must_remain_absent") is True:
        checks["employment_decision_not_generated"] = release.get("employment_decision_generated") is False

    summary_text = _extract_text(summary_path)
    checks["summary_minimum_words"] = _word_count(summary_text) >= int(spec.get("minimum_summary_words") or 1)
    signals = _signal_groups(summary_text, [list(group) for group in spec.get("summary_signal_groups") or []])
    checks["summary_domain_signals"] = all(signals.values())

    receipt = _load_json(receipt_path) if receipt_path.is_file() else {}
    archive = Path(str(receipt.get("archive") or ""))
    if archive.is_file():
        paths["archive"] = archive
        checks["archive_exists"] = archive.stat().st_size > 0

    artifacts = {
        key: _artifact_row(path, _extract_text(path), role=key)
        for key, path in paths.items()
    }
    return _base_receipt(
        product="VAMP Performance",
        spec=spec,
        source_path=native_binding_path,
        source_payload=binding,
        checks=checks,
        artifacts=artifacts,
        extra={"native_metrics": metrics, "signal_evidence": {"snapshot_summary": signals}},
        contract=contract,
    )


def audit_evidex_evidenceops(native_binding_path: Path, *, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = dict(contract or load_contract())
    spec = dict((contract.get("products") or {}).get("Evidex EvidenceOps") or {})
    if not spec:
        raise NativeProductQualityError("Evidex EvidenceOps native quality contract missing")
    native_binding_path = Path(native_binding_path).expanduser().resolve()
    binding = _load_json(native_binding_path)
    source_manifest_path = Path(str(binding.get("customer_source_manifest") or ""))
    source_manifest = _load_json(source_manifest_path) if source_manifest_path.is_file() else {}
    source_rows = [dict(row) for row in source_manifest.get("sources") or [] if isinstance(row, dict)]

    output_rows = [dict(row) for row in binding.get("native_output_files") or [] if isinstance(row, dict)]
    output_paths = [Path(str(row.get("path") or "")) for row in output_rows]
    existing_outputs = [path for path in output_paths if path.is_file()]
    total_output_bytes = sum(path.stat().st_size for path in existing_outputs)
    extractable_texts = [_extract_text(path) for path in existing_outputs]
    combined_text = " ".join(text for text in extractable_texts if text)

    checks: dict[str, bool] = {
        "native_binding_schema": binding.get("schema") == spec.get("native_binding_schema"),
        "native_engine_identity": binding.get("native_engine") == spec.get("native_engine"),
        "surrogate_fallback_forbidden": binding.get("surrogate_fallback_allowed") is False,
        "surrogate_fallback_unused": binding.get("surrogate_fallback_used") is False,
        "customer_source_manifest_present": source_manifest_path.is_file(),
        "minimum_customer_sources": len(source_rows) >= int(spec.get("minimum_customer_source_count") or 1),
        "source_hashes_distinct": len({str(row.get("sha256") or "") for row in source_rows if row.get("sha256")}) >= int(spec.get("minimum_customer_source_count") or 1),
        "minimum_output_files": len(existing_outputs) >= int(spec.get("minimum_output_file_count") or 1),
        "minimum_output_total_bytes": total_output_bytes >= int(spec.get("minimum_output_total_bytes") or 1),
        "minimum_extractable_words": _word_count(combined_text) >= int(spec.get("minimum_extractable_words") or 1),
    }
    signals = _signal_groups(combined_text, [list(group) for group in spec.get("output_signal_groups") or []])
    checks["output_domain_signals"] = all(signals.values())
    if spec.get("contradiction_must_be_preserved") is True:
        lower = combined_text.casefold()
        has_14 = "14" in lower or "fourteen" in lower
        has_12 = "12" in lower or "twelve" in lower
        has_gap_language = any(term in lower for term in ("gap", "unsupported", "missing", "only", "contradiction", "discrepancy"))
        checks["fourteen_vs_twelve_preserved"] = has_14 and has_12 and has_gap_language

    artifacts: dict[str, dict[str, Any]] = {
        "customer_source_manifest": _artifact_row(source_manifest_path, _extract_text(source_manifest_path), role="customer_source_manifest", showcase=False)
    }
    for index, path in enumerate(existing_outputs, 1):
        artifacts[f"output_{index:03d}"] = _artifact_row(
            path,
            _extract_text(path),
            role="evidex_customer_output",
            showcase=True,
        )

    return _base_receipt(
        product="Evidex EvidenceOps",
        spec=spec,
        source_path=native_binding_path,
        source_payload=binding,
        checks=checks,
        artifacts=artifacts,
        extra={
            "customer_source_count": len(source_rows),
            "native_output_file_count": len(existing_outputs),
            "native_output_total_bytes": total_output_bytes,
            "native_output_extractable_words": _word_count(combined_text),
            "signal_evidence": {"combined_outputs": signals},
        },
        contract=contract,
    )


def audit_product(product: str, native_receipt_path: Path, *, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    if product == "HOMS Exam":
        return audit_homs_exam(native_receipt_path, contract=contract)
    if product == "VAMP Performance":
        return audit_vamp_performance(native_receipt_path, contract=contract)
    if product == "Evidex EvidenceOps":
        return audit_evidex_evidenceops(native_receipt_path, contract=contract)
    raise NativeProductQualityError(f"no native artifact-quality auditor is registered for {product}")


__all__ = [
    "ACCEPTANCE_TOKEN",
    "CONTRACT_PATH",
    "NativeProductQualityError",
    "REFUSE_TOKEN",
    "SCHEMA",
    "audit_evidex_evidenceops",
    "audit_homs_exam",
    "audit_product",
    "audit_vamp_performance",
    "load_contract",
]

from __future__ import annotations

import hashlib
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


def _artifact_row(path: Path, text: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else 0,
        "sha256": _sha256(path) if path.is_file() else None,
    }
    if text is not None:
        row["word_count"] = _word_count(text)
    return row


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

    passed = all(checks.values())
    artifacts = {
        name: _artifact_row(path, texts.get(name) if name in texts else None)
        for name, path in paths.items()
    }
    artifacts["customer_source_booklet"] = _artifact_row(source_booklet)

    receipt = {
        "schema": SCHEMA,
        "product": "HOMS Exam",
        "route": spec.get("route"),
        "native_engine": spec.get("native_engine"),
        "native_receipt": str(native_receipt_path),
        "native_receipt_fingerprint": _fingerprint(native),
        "checks": checks,
        "signal_evidence": signal_evidence,
        "artifacts": artifacts,
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


__all__ = [
    "ACCEPTANCE_TOKEN",
    "CONTRACT_PATH",
    "NativeProductQualityError",
    "SCHEMA",
    "audit_homs_exam",
    "load_contract",
]

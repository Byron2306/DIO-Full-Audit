from __future__ import annotations

import copy
import hashlib
import html
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

from products.governed_case import canonical_hash, validate_case


PROFILE_SCHEMA = "dio.dossier_assembly.profile.v1"
PROCESSOR_ID = "controlled_dossier_assembly_v1"
ARTIFACT_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{1,79}")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write(path: Path, value: bytes) -> str:
    path.write_bytes(value)
    return _sha_bytes(value)


def _gate(case: dict[str, Any], gate_id: str) -> dict[str, Any]:
    return next(row for row in case["gates"] if row["gate_id"] == gate_id)


def _digest(value: str | None) -> str | None:
    if not value:
        return None
    return str(value).removeprefix("sha256:")


def validate_profile(profile: dict[str, Any]) -> None:
    if profile.get("schema") != PROFILE_SCHEMA:
        raise ValueError(f"Dossier assembly profile requires schema={PROFILE_SCHEMA}.")
    if not str(profile.get("profile_id") or "").strip():
        raise ValueError("Dossier assembly profile requires profile_id.")
    if not str(profile.get("product_id") or "").strip():
        raise ValueError("Dossier assembly profile requires product_id.")
    if profile.get("identity_state") != "genuine_profile_extension_unpromoted":
        raise ValueError("Dossier assembly profile must remain an unpromoted genuine profile extension.")
    if profile.get("canonical_portfolio_registration") is not False:
        raise ValueError("Dossier assembly profile cannot claim canonical portfolio registration.")
    if profile.get("document_studio_receipt_schema") != "dio.document_studio.receipt.v1":
        raise ValueError("Dossier assembly profile must bind the controlled Document Studio receipt schema.")
    if profile.get("authority_created") is not False:
        raise ValueError("Dossier assembly profile cannot create authority.")
    if profile.get("external_effects") is not False:
        raise ValueError("Dossier assembly profile cannot create external effects.")
    if profile.get("external_release") is not False:
        raise ValueError("Dossier assembly profile cannot grant external release.")


def _validate_document_studio_receipt(
    path: Path,
    *,
    expected_schema: str,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Document Studio receipt is not valid UTF-8 JSON: {path.name}") from exc

    if payload.get("schema") != expected_schema:
        raise ValueError("DossierOps requires a recognised Document Studio receipt schema.")
    if payload.get("status") != "human_review_required":
        raise ValueError("DossierOps only binds Document Studio artifacts that remain human-review gated.")

    release = payload.get("release") or {}
    if release.get("delivery_released") is not False:
        raise ValueError("DossierOps refuses a Document Studio receipt that claims delivery release.")
    if release.get("human_approval_required") is not True:
        raise ValueError("DossierOps requires Document Studio human approval to remain explicit.")
    if release.get("release_readiness") != "blocked_pending_human_approval":
        raise ValueError("DossierOps requires Document Studio release readiness to remain blocked.")

    return {
        "job_id": payload.get("job_id"),
        "status": payload.get("status"),
        "delivery_released": False,
        "human_approval_required": True,
        "release_readiness": release.get("release_readiness"),
    }


def _safe_artifact_id(value: Any) -> str:
    artifact_id = str(value or "").strip()
    if not ARTIFACT_ID_PATTERN.fullmatch(artifact_id):
        raise ValueError(
            "Dossier artifact_id must contain 2-80 letters, numbers, dots, underscores, or hyphens."
        )
    return artifact_id


def _render_index_html(index: dict[str, Any], *, title: str) -> bytes:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row['artifact_id']))}</td>"
        f"<td>{html.escape(str(row['artifact_type']))}</td>"
        f"<td>{html.escape(str(row['source_system']))}</td>"
        f"<td>{html.escape(str(row['approval_state']))}</td>"
        f"<td><code>{html.escape(str(row['sha256']))}</code></td>"
        "</tr>"
        for row in index["items"]
    )
    page = (
        "<!doctype html><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title>"
        f"<h1>{html.escape(title)}</h1>"
        "<p><strong>HUMAN DOSSIER REVIEW REQUIRED. EXTERNAL RELEASE REFUSED.</strong></p>"
        "<table border='1' cellspacing='0' cellpadding='6'>"
        "<tr><th>Artifact</th><th>Type</th><th>Source</th><th>Approval state</th><th>SHA-256</th></tr>"
        f"{rows}</table>"
        "<p>This assembly pack indexes and hash-binds supplied artifacts only. "
        "It creates no completeness, sufficiency, authenticity, retention, submission, "
        "release, or other consequential determination.</p>"
    )
    return page.encode("utf-8")


def run_controlled_dossier_assembly(
    case: dict[str, Any],
    *,
    profile: dict[str, Any],
    artifact_inputs: list[dict[str, Any]],
    output_dir: Path,
    operator_id: str,
    now: str,
) -> dict[str, Any]:
    validate_profile(profile)
    if case.get("product") != profile["product_id"]:
        raise ValueError(
            f"Dossier assembly profile {profile['profile_id']} requires product={profile['product_id']}."
        )
    if not str(operator_id or "").strip():
        raise ValueError("Controlled dossier assembly requires an explicit operator_id.")
    if _gate(case, "intake_authority")["state"] != "allow":
        raise RuntimeError("Controlled dossier assembly requires approved intake authority.")
    if _gate(case, "generic_executor")["state"] != "refuse":
        raise RuntimeError("Generic executor boundary drifted before controlled dossier assembly.")
    if _gate(case, "external_release")["state"] == "allow":
        raise RuntimeError("Controlled dossier assembly cannot start with external release ALLOW.")
    if not artifact_inputs:
        raise ValueError("Controlled dossier assembly requires at least one artifact input.")

    before = {
        field: copy.deepcopy(case[field])
        for field in ("gates", "actions", "decisions", "outputs")
    }
    validate_case(case)

    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError("Controlled dossier assembly output_dir must be empty.")
    items_dir = output_dir / "items"
    items_dir.mkdir(parents=True, exist_ok=True)

    ids: set[str] = set()
    items: list[dict[str, Any]] = []
    document_studio_receipts: list[dict[str, Any]] = []

    for item in artifact_inputs:
        artifact_id = _safe_artifact_id(item.get("artifact_id"))
        if artifact_id in ids:
            raise ValueError(f"Duplicate dossier artifact_id: {artifact_id}")
        ids.add(artifact_id)

        source_path = Path(str(item.get("path") or "")).expanduser().resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"Dossier artifact not found: {source_path}")
        if output_dir == source_path or output_dir in source_path.parents:
            raise ValueError("Dossier input artifacts cannot originate inside the assembly output directory.")

        source_sha = _sha_file(source_path)
        expected_sha = _digest(item.get("sha256"))
        if expected_sha and expected_sha != source_sha:
            raise ValueError(f"Dossier artifact hash mismatch: {artifact_id}")

        source_system = str(item.get("source_system") or "source_record").strip()
        artifact_type = str(item.get("artifact_type") or "record").strip()
        approval_state = str(item.get("approval_state") or "review_candidate").strip()

        document_studio_binding = None
        if source_system == "document_studio" and artifact_type == "document_studio_receipt":
            document_studio_binding = _validate_document_studio_receipt(
                source_path,
                expected_schema=str(profile["document_studio_receipt_schema"]),
            )
            document_studio_receipts.append(
                {
                    "artifact_id": artifact_id,
                    **document_studio_binding,
                }
            )

        suffix = "".join(source_path.suffixes) or ".bin"
        copied_name = f"{artifact_id}{suffix}"
        copied_path = items_dir / copied_name
        shutil.copyfile(source_path, copied_path)
        copied_sha = _sha_file(copied_path)
        if copied_sha != source_sha:
            raise RuntimeError(f"Dossier artifact copy hash drifted: {artifact_id}")

        items.append(
            {
                "artifact_id": artifact_id,
                "artifact_type": artifact_type,
                "source_system": source_system,
                "approval_state": approval_state,
                "source_name": source_path.name,
                "copied_path": str(copied_path.relative_to(output_dir)),
                "sha256": copied_sha,
                "document_studio_binding": document_studio_binding,
            }
        )

    items.sort(key=lambda row: row["artifact_id"])
    forbidden = {
        str(name): False for name in profile.get("forbidden_outcomes") or []
    }
    index = {
        "schema": "dio.dossier_assembly.index.v1",
        "profile_id": profile["profile_id"],
        "product_id": profile["product_id"],
        "case_id": case["case_id"],
        "items": items,
        "document_studio_binding": {
            "receipt_count": len(document_studio_receipts),
            "receipts": document_studio_receipts,
            "document_studio_execution_performed": False,
            "binding_kind": "validated_review_artifact_input",
        },
        "human_review": {
            "dossier_completeness": "NEEDS_YOU",
            "record_sufficiency": "NEEDS_YOU",
            "final_release": "NEEDS_YOU",
        },
        "forbidden_outcomes_created": forbidden,
        "authority_created": False,
        "external_effects": False,
        "external_release": "REFUSE",
    }

    prefix = str(profile.get("artifact_prefix") or profile["profile_id"]).upper().replace("-", "_")
    title = str(
        profile.get("review_pack_title")
        or f"{profile['profile_id']} Controlled Assembly Pack"
    )
    index_json_name = f"{prefix}_DOSSIER_INDEX.json"
    index_html_name = f"{prefix}_DOSSIER_INDEX.html"
    index_json = json.dumps(index, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"
    index_html = _render_index_html(index, title=title)
    index_json_sha = _write(output_dir / index_json_name, index_json)
    index_html_sha = _write(output_dir / index_html_name, index_html)

    proof_artifacts = [
        {
            "artifact_type": "DOSSIER_ITEM",
            "filename": row["copied_path"],
            "sha256": row["sha256"],
        }
        for row in items
    ]
    proof_artifacts.extend(
        [
            {
                "artifact_type": "DOSSIER_INDEX_JSON",
                "filename": index_json_name,
                "sha256": index_json_sha,
            },
            {
                "artifact_type": "DOSSIER_INDEX_HTML",
                "filename": index_html_name,
                "sha256": index_html_sha,
            },
        ]
    )

    proof = {
        "schema": "dio.dossier_assembly.controlled_proof_manifest.v1",
        "processor_id": PROCESSOR_ID,
        "profile_id": profile["profile_id"],
        "product_id": profile["product_id"],
        "case_id": case["case_id"],
        "case_sha256": canonical_hash(case),
        "index_fingerprint": "sha256:" + _sha_bytes(_canonical(index)),
        "artifacts": proof_artifacts,
        "document_studio_binding": index["document_studio_binding"],
        "human_gate": {
            "state": "NEEDS_YOU",
            "reason": str(
                profile.get("human_gate_reason")
                or "Dossier review and release remain human-authority bound."
            ),
        },
        "forbidden_outcomes_created": forbidden,
        "authority_created": False,
        "execution_performed": False,
        "external_effects": False,
        "external_release": False,
    }
    proof["proof_fingerprint"] = "sha256:" + _sha_bytes(_canonical(proof))
    proof_name = "PROOF_MANIFEST.json"
    proof_sha = _write(
        output_dir / proof_name,
        json.dumps(proof, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n",
    )

    bundle_name = f"{prefix}_CONTROLLED_DOSSIER.zip"
    bundle_path = output_dir / bundle_name
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for row in items:
            bundle.write(output_dir / row["copied_path"], row["copied_path"])
        bundle.write(output_dir / index_json_name, index_json_name)
        bundle.write(output_dir / index_html_name, index_html_name)
        bundle.write(output_dir / proof_name, proof_name)
    bundle_sha = _sha_file(bundle_path)

    receipt = {
        "schema": "dio.dossier_assembly.controlled_processing_receipt.v1",
        "processor_id": PROCESSOR_ID,
        "profile_id": profile["profile_id"],
        "product_id": profile["product_id"],
        "case_id": case["case_id"],
        "operator_id": operator_id,
        "processed_at": now,
        "internal_processing": "COMPLETE",
        "assembly_performed": True,
        "product_execution_proved": False,
        "generic_executor_gate": _gate(case, "generic_executor")["state"],
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "document_studio_receipt_count": len(document_studio_receipts),
        "document_studio_execution_performed": False,
        "index_fingerprint": proof["index_fingerprint"],
        "proof_fingerprint": proof["proof_fingerprint"],
        "proof_manifest_sha256": proof_sha,
        "bundle": {
            "filename": bundle_name,
            "sha256": bundle_sha,
            "contains_processing_receipt": False,
        },
        "forbidden_outcomes_created": forbidden,
        "authority_created": False,
        "execution_performed": False,
        "external_effects": False,
        "external_release": False,
    }
    receipt_name = f"{prefix}_PROCESSING_RECEIPT.json"
    _write(
        output_dir / receipt_name,
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n",
    )

    for field in before:
        if case[field] != before[field]:
            raise RuntimeError(f"Controlled dossier assembly illegally mutated case {field}.")
    validate_case(case)

    return {
        "case": case,
        "dossier_index": index,
        "proof_manifest": proof,
        "receipt": receipt,
        "output_dir": str(output_dir),
        "bundle_path": str(bundle_path),
    }

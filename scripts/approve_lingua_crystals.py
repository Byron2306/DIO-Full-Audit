#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts" / "lingua_beast_bridge.py"


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reconcile_pack_approval(
    *,
    semantic_object: dict[str, Any],
    approval: dict[str, Any],
    approval_path: Path,
    beast_receipt_path: Path,
) -> list[str]:
    """Project semantic approval into every matching product review pack."""
    object_id = str(approval["semantic_object_id"])
    language = str(approval["target_language"])
    updated_packs = []
    for lingua_qa_path in ROOT.glob("deliverables/**/LINGUA_QA.json"):
        pack = lingua_qa_path.parent
        object_copy_path = pack / "LINGUA_SEMANTIC_OBJECT.json"
        if not object_copy_path.is_file():
            continue
        object_copy = json.loads(object_copy_path.read_text(encoding="utf-8"))
        if object_copy.get("object_id") != object_id:
            continue
        lingua_qa = json.loads(lingua_qa_path.read_text(encoding="utf-8"))
        if lingua_qa.get("target_language") != language:
            continue
        resolutions = [
            resolution
            for unit in approval.get("units") or []
            for resolution in unit.get("flag_resolutions") or []
        ]
        lingua_qa.update({
            "linguistic_quality_approved": True,
            "review_required": False,
            "release_readiness": "semantic_approved",
            "semantic_authority": "human_approved_crystallized",
            "reviewer": approval["reviewer"],
            "reviewer_role": approval["reviewer_role"],
            "approved_at": approval["approved_at"],
            "flag_dispositions": {
                key: sum(item.get("resolution") == key for item in resolutions)
                for key in ("accepted_as_is", "corrected", "not_applicable")
            },
        })
        atomic_json(lingua_qa_path, lingua_qa)
        atomic_json(object_copy_path, semantic_object)
        atomic_json(pack / "LINGUA_HUMAN_APPROVAL.json", approval)
        shutil.copy2(beast_receipt_path, pack / "LINGUA_BEAST_APPROVAL_RECEIPT.json")

        document_qa_path = pack / "DOCUMENT_STUDIO_QA.json"
        if document_qa_path.is_file():
            document_qa = json.loads(document_qa_path.read_text(encoding="utf-8"))
            document_qa["linguistic_quality_approved"] = True
            document_qa["release_readiness"] = "linguistic_approved_pending_remaining_review"
            document_qa.setdefault("human_gates", {})["target_language_reviewer_approval"] = "approved"
            overrides = document_qa.setdefault("translation_review_overrides", {})
            overrides["reviewer"] = approval["reviewer"]
            overrides["reviewer_role"] = approval["reviewer_role"]
            overrides["approved_at"] = approval["approved_at"]
            existing_corrections = list(overrides.get("corrections") or [])
            provider_output_path = pack / "PROVIDER_OUTPUT.json"
            if not existing_corrections and provider_output_path.is_file():
                provider_output = json.loads(provider_output_path.read_text(encoding="utf-8"))
                existing_corrections = [
                    {
                        "paragraph_id": row.get("paragraph_id"),
                        "before": row.get("model_draft"),
                        "after": row.get("translated"),
                        "reason": row.get("review_note") or "Bilingual proof-review correction",
                    }
                    for row in provider_output.get("translations") or []
                    if row.get("review_override_applied")
                ]
            approval_corrections = [item for item in resolutions if item.get("resolution") == "corrected"]
            overrides["applied_count"] = max(
                int(overrides.get("applied_count") or 0),
                len(existing_corrections) + len(approval_corrections),
            )
            overrides["corrections"] = existing_corrections + approval_corrections
            overrides["final_language_approval_still_required"] = False
            atomic_json(document_qa_path, document_qa)

        document_receipt_path = pack / "DOCUMENT_STUDIO_RECEIPT.json"
        if document_receipt_path.is_file():
            document_receipt = json.loads(document_receipt_path.read_text(encoding="utf-8"))
            document_receipt["status"] = "linguistic_approved_pending_remaining_review"
            release = document_receipt.setdefault("release", {})
            release["linguistic_quality_approved"] = True
            release["release_readiness"] = "linguistic_approved_pending_remaining_review"
            release["language_reviewer"] = approval["reviewer"]
            release["language_approved_at"] = approval["approved_at"]
            document_receipt["outputs"] = [
                {"path": str(path.relative_to(pack)), "sha256": sha256(path)}
                for path in sorted(pack.rglob("*"))
                if path.is_file()
                and path != document_receipt_path
                and not path.name.endswith("_DOCUMENT_STUDIO_REVIEW_PACK.zip")
            ]
            atomic_json(document_receipt_path, document_receipt)

        archives = list(pack.glob("*_DOCUMENT_STUDIO_REVIEW_PACK.zip"))
        for archive in archives:
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                for path in sorted(pack.rglob("*")):
                    if path.is_file() and path != archive:
                        bundle.write(path, path.relative_to(pack))
        updated_packs.append(str(pack))
    return updated_packs


def crystallize_approval(approval_path: Path) -> Path:
    approval_path = approval_path.expanduser().resolve()
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if approval.get("schema") != "dio.lingua.human_approval.v1":
        raise ValueError("Unsupported Lingua approval schema.")
    if approval.get("approval_state") != "approved":
        raise PermissionError("approval_state must be approved before crystallization.")
    if not str(approval.get("reviewer") or "").strip() or not str(approval.get("reviewer_role") or "").strip():
        raise ValueError("reviewer and reviewer_role are required.")
    units = list(approval.get("units") or [])
    if not units or any(not row.get("approved") or not str(row.get("target_text") or "").strip() for row in units):
        raise PermissionError("Every translation unit must be explicitly approved with final target text.")
    terms = list(approval.get("terms") or [])
    if any(not row.get("approved") or not row.get("source_term") or not row.get("target_term") for row in terms):
        raise PermissionError("Every terminology entry must be explicitly approved.")
    object_id = str(approval.get("semantic_object_id") or "")
    object_path = ROOT / "state" / "lingua" / "objects" / f"{object_id}.json"
    semantic_object = json.loads(object_path.read_text(encoding="utf-8"))
    language = str(approval.get("target_language") or "")
    lane = semantic_object.get("translations", {}).get(language)
    if not lane:
        raise ValueError("The semantic object does not contain the requested target-language lane.")
    source_hashes = {row["unit_id"]: row["source_hash"] for row in semantic_object["source"]["units"]}
    lane_unit_ids = {str(row.get("unit_id") or "") for row in lane.get("units") or []}
    approval_unit_ids = {str(row.get("unit_id") or "") for row in units}
    if approval_unit_ids != lane_unit_ids:
        raise PermissionError("Approval must cover every current translation unit exactly once.")
    for row in units:
        if source_hashes.get(row["unit_id"]) != row.get("source_hash"):
            raise PermissionError(f"Source changed before approval: {row['unit_id']}")
        for flag in row.get("flag_resolutions") or []:
            if flag.get("resolution") not in {"accepted_as_is", "corrected", "not_applicable"}:
                raise PermissionError(f"Every material flag requires a final disposition: {row['unit_id']}")
    completed = subprocess.run(
        [sys.executable, str(BRIDGE)],
        input=json.dumps({"operation": "crystallize", **approval}),
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
        cwd=ROOT,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"BEAST crystallization failed: {completed.stdout[-1200:] or completed.stderr[-1200:]}")
    receipt = json.loads(completed.stdout)
    approved_by_id = {row["unit_id"]: row for row in units}
    for row in lane["units"]:
        approved = approved_by_id[row["unit_id"]]
        row["target_text"] = approved["target_text"]
        row["status"] = "human_approved_crystallized"
        row["reviewer"] = approval["reviewer"]
        row["approved_at"] = approval["approved_at"]
        row["flag_resolutions"] = approved.get("flag_resolutions") or []
    lane["status"] = "human_approved_crystallized"
    lane["review"] = {
        "reviewer": approval["reviewer"],
        "reviewer_role": approval["reviewer_role"],
        "approved_at": approval["approved_at"],
        "approval_path": str(approval_path),
    }
    semantic_object["authority"]["last_approved_language"] = language
    semantic_object["authority"]["last_crystallization_receipt"] = receipt
    semantic_object["updated_at"] = approval["approved_at"]
    atomic_json(object_path, semantic_object)
    receipt_path = approval_path.with_name(f"{approval_path.stem}_BEAST_RECEIPT.json")
    atomic_json(receipt_path, receipt)
    reconcile_pack_approval(
        semantic_object=semantic_object,
        approval=approval,
        approval_path=approval_path,
        beast_receipt_path=receipt_path,
    )
    return receipt_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Crystallize a proficient human's approved DIO Lingua units into BEAST.")
    parser.add_argument("approval", type=Path)
    args = parser.parse_args()
    receipt_path = crystallize_approval(args.approval)
    print(receipt_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

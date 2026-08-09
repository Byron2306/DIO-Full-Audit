#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.document_studio.pipeline import (  # noqa: E402
    _row_map,
    apply_beast_authority,
    learn_beast_patterns,
    normalize_language_request,
    paragraphs_from_text,
    resolve_beast_context,
    sha256,
    validate_result,
    write_json,
)
from adapters.lingua.lifecycle import build_lingua_qa, update_semantic_object  # noqa: E402
from adapters.sophia.review_pipeline import extract_document_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Attach DIO Lingua and BEAST lifecycle artifacts to an existing Document Studio pack.")
    parser.add_argument("request", type=Path)
    parser.add_argument("pack", type=Path)
    args = parser.parse_args()
    request_path = args.request.expanduser().resolve()
    pack = args.pack.expanduser().resolve()
    request = normalize_language_request(json.loads(request_path.read_text(encoding="utf-8")))
    source_path = Path(str(request["document_path"]))
    if not source_path.is_absolute():
        source_path = (request_path.parent / source_path).resolve()
    text, _parser = extract_document_text(source_path)
    paragraphs = paragraphs_from_text(text)
    result_path = pack / "PROVIDER_OUTPUT.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    receipt_path = pack / "DOCUMENT_STUDIO_RECEIPT.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    provider = {
        "provider": receipt.get("processing", {}).get("provider"),
        "model": receipt.get("processing", {}).get("model"),
    }
    beast_receipt = resolve_beast_context(request, paragraphs)
    apply_beast_authority(result, beast_receipt)
    validation = validate_result(request, paragraphs, result)
    beast_learning_receipt = learn_beast_patterns(request, result, validation)
    if not validation["passed"]:
        raise ValueError("Existing provider output failed current validation: " + "; ".join(validation["errors"]))
    translations = _row_map(list(result.get("translations") or []), "translated")
    object_id = str(request.get("semantic_object_id") or f"LINGUA-{request['job_id']}")
    source_version = str(request.get("source_version") or "1.0.0")
    semantic_object, change_receipt = update_semantic_object(
        state_root=ROOT / "state" / "lingua",
        object_id=object_id,
        source_version=source_version,
        request=request,
        source_rows=paragraphs,
        translations=translations,
        provider=provider,
        qa_flags=list(result.get("qa_flags") or []),
    )
    lingua_qa = build_lingua_qa(request, validation, result, beast_receipt)
    approval_template = {
        "schema": "dio.lingua.human_approval.v1",
        "approval_state": "pending",
        "semantic_object_id": object_id,
        "source_version": source_version,
        "target_language": request["target_language"],
        "domain": request.get("document_domain"),
        "reviewer": "",
        "reviewer_role": "",
        "approved_at": "",
        "units": [
            {
                "unit_id": unit["unit_id"],
                "source_hash": unit["source_hash"],
                "target_text": translation["target_text"],
                "approved": False,
            }
            for unit, translation in zip(
                semantic_object["source"]["units"],
                semantic_object["translations"][request["target_language"]]["units"],
            )
        ],
        "terms": [],
        "authority_note": "A proficient target-language reviewer must correct the text, approve every unit, and identify their role before BEAST crystallization.",
    }
    write_json(result_path, result)
    write_json(pack / "BEAST_REUSE_RECEIPT.json", beast_receipt)
    write_json(pack / "BEAST_LEARNING_RECEIPT.json", beast_learning_receipt)
    write_json(pack / "LINGUA_SEMANTIC_OBJECT.json", semantic_object)
    write_json(pack / "LINGUA_CHANGE_RECEIPT.json", change_receipt)
    write_json(pack / "LINGUA_QA.json", lingua_qa)
    write_json(pack / "LINGUA_APPROVAL_TEMPLATE.json", approval_template)
    qa_path = pack / "DOCUMENT_STUDIO_QA.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    qa["automated_integrity_passed"] = validation["passed"]
    qa["linguistic_quality_approved"] = False
    qa["release_readiness"] = "blocked_pending_human_approval"
    qa.setdefault("language_controls", {})["beast_reuse"] = beast_receipt
    write_json(qa_path, qa)
    receipt.setdefault("processing", {})["beast_reuse_state"] = beast_receipt["reuse_state"]
    receipt["processing"]["beast_learning_count"] = len(beast_learning_receipt.get("learned") or [])
    receipt["processing"]["semantic_object_id"] = object_id
    receipt.setdefault("release", {})["linguistic_quality_approved"] = False
    receipt["release"]["release_readiness"] = "blocked_pending_human_approval"
    archive = pack / f"{request['job_id']}_DOCUMENT_STUDIO_REVIEW_PACK.zip"
    receipt["outputs"] = [
        {"path": str(path.relative_to(pack)), "sha256": sha256(path)}
        for path in sorted(pack.rglob("*"))
        if path.is_file() and path not in {archive, receipt_path}
    ]
    write_json(receipt_path, receipt)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(pack.rglob("*")):
            if path.is_file() and path != archive:
                bundle.write(path, path.relative_to(pack))
    print(pack)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

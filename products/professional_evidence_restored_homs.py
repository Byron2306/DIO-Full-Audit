from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from portfolio_runtime import ROOT
from products.professional_evidence_native_routes import (
    DEFAULT_HYMARK_BACKEND,
    DEFAULT_HYMARK_NATIVE_PYTHON,
    DEFAULT_HYMARK_SECRET_FILE,
    SCHEMA,
    _homs_exam_request,
    _interpreter_path,
    _isolated_native_env,
    _preflight_hymark_runtime,
    _require_native_outputs,
)
from products.professional_evidence_projection import sha256, write_json


SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(SCRIPT_DIR))

from attach_homs_source_assets import CURATED_DEFAULT_BANK, priority_key, to_pack_source_asset  # type: ignore  # noqa: E402


ENGINE_IDENTITY = "scripts.run_hymark_history_source_first.run_builder"
SOURCE_BANK_SCHEMA = "knowedge.homs_core_source_bank_curated.v1"
RESTORED_SOURCE_SCHEMA = "dio.homs.native_source_federation.v2"
STOPWORDS = {
    "about", "after", "again", "against", "also", "and", "are", "been", "being", "build", "customer",
    "from", "grade", "history", "into", "more", "must", "paper", "source", "sources", "south", "that",
    "their", "this", "through", "with", "within", "year", "years",
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]{4,}", str(value or "").casefold())
        if token not in STOPWORDS
    }


def _load_curated_bank() -> dict[str, Any]:
    path = CURATED_DEFAULT_BANK.expanduser().resolve()
    if not path.is_file():
        return {"schema": SOURCE_BANK_SCHEMA, "assets": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != SOURCE_BANK_SCHEMA:
        raise RuntimeError("HOMS curated source bank schema mismatch")
    return payload


def _select_topic_bound_assets(request: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    """Bind real source-bank assets only when they actually match the job topic."""
    bank = _load_curated_bank()
    query = " ".join(
        [
            *[str(item) for item in request.get("topics") or []],
            str(request.get("methodology_topic") or ""),
            str(request.get("essay_topic") or ""),
        ]
    )
    query_tokens = _tokens(query)
    candidates: list[tuple[int, dict[str, Any]]] = []
    for asset in bank.get("assets") or []:
        if asset.get("subject_id") != "history":
            continue
        preferred = ROOT / str(asset.get("preferred_png") or "")
        if not preferred.is_file():
            continue
        asset_blob = " ".join(
            [
                str(asset.get("paper") or ""),
                str(asset.get("paper_theme") or ""),
                str(asset.get("snippet") or ""),
                str(asset.get("object_id") or ""),
            ]
        )
        overlap = len(query_tokens & _tokens(asset_blob))
        if overlap >= 2:
            candidates.append((overlap, asset))

    selected: list[dict[str, Any]] = []
    used_types: set[str] = set()
    for _score, asset in sorted(
        candidates,
        key=lambda item: (-item[0], priority_key(item[1], ["text_extract", "photograph_or_image", "cartoon", "data_table"])),
    ):
        source_type = str(asset.get("source_type") or "")
        if source_type in used_types:
            continue
        selected.append(asset)
        used_types.add(source_type)
        if len(selected) >= limit:
            break
    return selected


def _source_manifest(selected_assets: list[dict[str, Any]], source_booklet: Path) -> dict[str, Any]:
    rows = []
    for index, asset in enumerate(selected_assets, 1):
        row = to_pack_source_asset(asset, index)
        preferred = ROOT / str(row.get("preferred_png") or "")
        rows.append(
            {
                **row,
                "preferred_png_absolute": str(preferred.resolve()),
                "preferred_png_sha256": sha256(preferred),
                "controlled_review_only": True,
                "human_source_review_required": True,
            }
        )
    return {
        "schema": RESTORED_SOURCE_SCHEMA,
        "source_bank": str(CURATED_DEFAULT_BANK),
        "customer_source_booklet": str(source_booklet.resolve()),
        "customer_source_booklet_sha256": sha256(source_booklet),
        "selected_asset_count": len(rows),
        "selected_assets": rows,
        "source_asset_policy": (
            "Customer source text is authoritative. Existing curated HOMS assets may be embedded only when topic-bound. "
            "An unrelated old-paper image is not decoration, and a missing image may never be replaced by prose description."
        ),
        "public_release": "REFUSE",
        "human_source_review": "NEEDS_YOU",
        "authority_created": False,
    }


def _harden_request(base: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    request = dict(base)
    request["dio_homs_source_federation"] = manifest
    request["additional_instructions"] = (
        str(request.get("additional_instructions") or "").rstrip()
        + "\n\nDIO HOMS SOURCE-FIRST LAW:\n"
        + "- Customer source text is immutable learner evidence.\n"
        + "- Questions and memoranda may be generated; source content and provenance may not.\n"
        + "- No fictional historian, invented quotation, author, date, publication, photograph, cartoon, map or image is permitted.\n"
        + "- If a real topic-bound visual is not present in dio_homs_source_federation, the examination must remain text-source based.\n"
        + "- Document Studio owns final source placement and formatting."
    )
    return request


def run_restored_homs_exam(packet: dict[str, Any], execution_dir: Path, *, now: str) -> dict[str, Any]:
    source_booklet = Path(packet["packet_dir"]) / "SOURCES" / "source_pack.md"
    if not source_booklet.is_file():
        raise RuntimeError("HOMS Exam requires the Vesper-custodied customer source booklet")

    projection_dir = execution_dir.parent / "PROJECTION"
    base_request = _homs_exam_request(packet, source_booklet)
    selected_assets = _select_topic_bound_assets(base_request)
    manifest = _source_manifest(selected_assets, source_booklet)
    request = _harden_request(base_request, manifest)
    request_path = projection_dir / "HYMARK_NATIVE_EXAM_REQUEST.json"
    write_json(request_path, request)
    write_json(projection_dir / "HOMS_NATIVE_SOURCE_FEDERATION.json", manifest)

    native_python = _interpreter_path(Path(os.environ.get("HOMS_EXAM_PYTHON") or DEFAULT_HYMARK_NATIVE_PYTHON))
    backend = Path(os.environ.get("HOMS_HYMARK_BACKEND") or DEFAULT_HYMARK_BACKEND).expanduser().resolve()
    secret_file = Path(os.environ.get("HOMS_SECRET_FILE") or DEFAULT_HYMARK_SECRET_FILE).expanduser().resolve()
    if not native_python.is_file():
        raise FileNotFoundError(f"HOMS native HyMark Python missing: {native_python}")
    if not backend.is_file():
        raise FileNotFoundError(f"HOMS native HyMark backend missing: {backend}")
    runtime_preflight = _preflight_hymark_runtime(native_python, backend)

    native_root = execution_dir / "hymark_native"
    command = [
        str(native_python),
        str(ROOT / "scripts" / "run_hymark_history_source_first.py"),
        "--request",
        str(request_path),
        "--out",
        str(native_root),
        "--secret-file",
        str(secret_file),
        "--backend",
        str(backend),
        "--provider",
        os.environ.get("HOMS_PROVIDER", "nim"),
        "--opportunities",
        "both",
    ]
    model = os.environ.get("HOMS_MODEL", "").strip()
    if model:
        command.extend(["--model", model])

    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=_isolated_native_env(native_python),
        timeout=int(os.environ.get("HOMS_NATIVE_TIMEOUT_SECONDS", "1800")),
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "HOMS source-first native runtime failed: "
            + (completed.stderr or completed.stdout or "no diagnostic output")[-6000:]
        )

    receipt_paths = sorted(native_root.rglob("HYMARK_EXAM_BUILDER_RECEIPT.json"))
    if len(receipt_paths) != 1:
        raise RuntimeError(f"HOMS source-first route expected one native receipt, found {len(receipt_paths)}")
    native_receipt = json.loads(receipt_paths[0].read_text(encoding="utf-8"))
    if ((native_receipt.get("assessor") or {}).get("native_engine")) != ENGINE_IDENTITY:
        raise RuntimeError("HOMS source-first receipt reported the wrong native engine identity")
    outputs = _require_native_outputs(native_receipt)

    first_hash = sha256(outputs["first_exam"])
    second_hash = sha256(outputs["second_exam"])
    if first_hash == second_hash:
        raise RuntimeError("HOMS source-first builder produced identical opportunity papers")

    binding = {
        "schema": SCHEMA,
        "incarnation": "HOMS Exam",
        "route": "homs_raw_exam",
        "native_engine": ENGINE_IDENTITY,
        "native_runtime_python": str(native_python),
        "native_runtime_preflight": runtime_preflight,
        "native_receipt_schema": native_receipt.get("schema"),
        "native_receipt_path": str(receipt_paths[0]),
        "native_job_id": native_receipt.get("job_id"),
        "native_generation_backend": ((native_receipt.get("assessor") or {}).get("generation_backend")),
        "native_output_hashes": {name: sha256(path) for name, path in outputs.items()},
        "customer_packet_fingerprint": packet.get("packet_fingerprint"),
        "customer_source_booklet_sha256": sha256(source_booklet),
        "source_federation": manifest,
        "source_matrix_and_bank_connected": True,
        "customer_source_text_locked_before_question_generation": True,
        "described_missing_visual_allowed": False,
        "invented_source_provenance_allowed": False,
        "native_capability_preserved": True,
        "surrogate_fallback_allowed": False,
        "surrogate_fallback_used": False,
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    write_json(execution_dir / "HOMS_NATIVE_ROUTE_BINDING.json", binding)
    return {
        "executor": ENGINE_IDENTITY,
        "native_engine_identity": ENGINE_IDENTITY,
        "native_capability_preserved": True,
        "surrogate_fallback_used": False,
        "product_id": "homs_exam",
        "terminal_artifact_kind": "native_hymark_source_first_exam_and_memoranda_pack",
        "product_pipeline_executed": True,
        "domain_action_executed": False,
        "receipt": binding,
        "native_result": native_receipt,
    }


__all__ = ["ENGINE_IDENTITY", "RESTORED_SOURCE_SCHEMA", "run_restored_homs_exam"]

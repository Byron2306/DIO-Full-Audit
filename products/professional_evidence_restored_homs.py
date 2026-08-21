from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from portfolio_runtime import ROOT
from products.professional_evidence_native_routes import (
    DEFAULT_HYMARK_BACKEND,
    DEFAULT_HYMARK_NATIVE_PYTHON,
    DEFAULT_HYMARK_SECRET_FILE,
    NATIVE_ENGINE_ROUTES,
    SCHEMA,
    _homs_exam_request,
    _interpreter_path,
    _isolated_native_env,
    _preflight_hymark_runtime,
    _require_native_outputs,
)
from products.professional_evidence_projection import sha256, write_json


SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from apply_homs_design_law import (  # type: ignore  # noqa: E402
    DEFAULT_ASSESSMENT_DESIGN,
    DEFAULT_DESIGN_LAW,
    apply_design_law,
    assessment_design_for_pack,
    load_json as load_design_json,
    render_docx,
)
from attach_homs_source_assets import (  # type: ignore  # noqa: E402
    CURATED_DEFAULT_BANK,
    priority_key,
    requested_source_types,
    to_pack_source_asset,
)


SOURCE_BANK_SCHEMA = "knowedge.homs_core_source_bank_curated.v1"
RESTORED_SOURCE_SCHEMA = "dio.homs.native_source_federation.v1"
VISUAL_SOURCE_TYPES = {"photograph_or_image", "cartoon", "map_extract", "graph_or_chart", "diagram_or_model"}
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
    """Select only real History assets with a meaningful topic overlap.

    The source bank is a fidelity/content source, not a decoration library. An
    unrelated official-paper photograph may not be inserted merely because a
    visual source is aesthetically desirable.
    """
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
        if overlap < 2:
            continue
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


def _source_manifest(request: dict[str, Any], selected_assets: list[dict[str, Any]], source_booklet: Path) -> dict[str, Any]:
    rows = []
    for index, asset in enumerate(selected_assets, 1):
        row = to_pack_source_asset(asset, index)
        path = ROOT / str(row.get("preferred_png") or "")
        rows.append(
            {
                **row,
                "preferred_png_absolute": str(path.resolve()),
                "preferred_png_sha256": sha256(path),
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
            "Only topic-bound real assets may be embedded. If no suitable real visual is bound, HyMark must use the literal "
            "customer text sources and may not invent a photograph, cartoon, map, image, author, date, quotation, or provenance."
        ),
        "public_release": "REFUSE",
        "human_source_review": "NEEDS_YOU",
        "authority_created": False,
    }


def _harden_request(request: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    request = dict(request)
    assets = list(manifest.get("selected_assets") or [])
    asset_lines = []
    for index, asset in enumerate(assets, 1):
        asset_lines.append(
            f"BOUND SOURCE ASSET {index}: type={asset.get('source_type')}; paper={asset.get('paper')}; "
            f"page={asset.get('page')}; object_id={asset.get('object_id')}; snippet={asset.get('snippet')}"
        )
    visual_types = sorted({str(row.get("source_type") or "") for row in assets if str(row.get("source_type") or "") in VISUAL_SOURCE_TYPES})
    hard_law = "\n".join(
        [
            "DIO HOMS SOURCE LAW:",
            "- The customer source booklet is byte-authoritative. Use its supplied source wording; do not expand a short source into an invented historical quotation.",
            "- Do not invent an author, historian, photographer, publication, date, quotation, caption, or source provenance that is absent from the customer booklet or a bound source asset.",
            "- Never write 'fictional', 'based on real historiography', or an invented source presented as classroom evidence.",
            "- A photograph/cartoon/map/graph/image may appear only when a real bound visual asset of that type is listed below and will be embedded by Document Studio.",
            "- If no real visual asset is bound, use the supplied text sources only. Do not describe a missing picture in prose and then ask learners to analyse it.",
            f"- Bound visual source types: {', '.join(visual_types) if visual_types else 'NONE'}.",
            *asset_lines,
        ]
    )
    request["additional_instructions"] = str(request.get("additional_instructions") or "").rstrip() + "\n\n" + hard_law
    request["dio_homs_source_federation"] = manifest
    return request


def _pack_text(pack: dict[str, Any]) -> str:
    return json.dumps(pack, ensure_ascii=False, sort_keys=True)


def _source_integrity_errors(pack: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    blob = _pack_text(pack)
    lower = blob.casefold()
    errors: list[str] = []
    for forbidden in ("fictional excerpt", "based on real historiography", "fictional source"):
        if forbidden in lower:
            errors.append(f"learner pack contains forbidden invented-source marker: {forbidden}")
    bound_visual_types = {
        str(row.get("source_type") or "")
        for row in manifest.get("selected_assets") or []
        if str(row.get("source_type") or "") in VISUAL_SOURCE_TYPES
    }
    visual_words = {
        "photograph_or_image": ("photograph", "photo", "image"),
        "cartoon": ("cartoon",),
        "map_extract": (" map ", "map extract"),
        "graph_or_chart": ("graph", "chart"),
        "diagram_or_model": ("diagram",),
    }
    for source_type, words in visual_words.items():
        if source_type in bound_visual_types:
            continue
        if any(word in f" {lower} " for word in words):
            # Visual-blueprint metadata itself can name a visual kind. Restrict
            # the hard failure to learner-facing section material.
            section_blob = json.dumps(pack.get("sections") or [], ensure_ascii=False).casefold()
            if any(word in f" {section_blob} " for word in words):
                errors.append(f"learner pack references {source_type} but no real bound asset exists")
    return sorted(set(errors))


def _docx_embedded_image_count(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        with zipfile.ZipFile(path) as archive:
            return len([name for name in archive.namelist() if name.startswith("word/media/")])
    except zipfile.BadZipFile:
        return 0


def _attach_sources_and_rerender(
    opportunity_dir: Path,
    exam_path: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    pack_path = opportunity_dir / "assessment_pack.json"
    if not pack_path.is_file():
        raise RuntimeError(f"HOMS source federation cannot find assessment pack: {pack_path}")
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    errors = _source_integrity_errors(pack, manifest)
    if errors:
        raise RuntimeError("HOMS source-integrity gate refused learner pack: " + "; ".join(errors))

    selected = list(manifest.get("selected_assets") or [])
    if selected:
        pack["source_assets"] = [
            {key: value for key, value in row.items() if key not in {"preferred_png_absolute", "preferred_png_sha256"}}
            for row in selected
        ]
        pack.setdefault("source_embedding", {})
        pack["source_embedding"].update(
            {
                "schema": "knowedge.homs_source_embedding.v1",
                "source_bank": str(CURATED_DEFAULT_BANK.relative_to(ROOT)),
                "asset_count": len(selected),
                "generated_visual_policy": "suppress_generated_visuals_when_source_assets_present",
                "policy": "Real topic-bound source assets are embedded for controlled human review; no invented visual substitute is permitted.",
                "release_gate": "NEEDS_YOU",
            }
        )
        pack_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        design_receipt = apply_design_law(opportunity_dir, DEFAULT_DESIGN_LAW, DEFAULT_ASSESSMENT_DESIGN)
        design_law = load_design_json(DEFAULT_DESIGN_LAW)
        design_payload = load_design_json(DEFAULT_ASSESSMENT_DESIGN)
        assessment_design = assessment_design_for_pack(pack, design_payload)
        output_name = "ASSESSMENT_LEARNER_RESTORED.docx"
        restored = render_docx(
            opportunity_dir,
            pack,
            design_law,
            design_receipt.get("assets") or [],
            assessment_design,
            include_memo_sections=False,
            output_name=output_name,
        )
        shutil.copy2(restored, exam_path)

    embedded_images = _docx_embedded_image_count(exam_path)
    if selected and embedded_images < 1:
        raise RuntimeError("HOMS source federation selected real visual assets but final learner DOCX contains no embedded image")
    receipt = {
        "schema": RESTORED_SOURCE_SCHEMA,
        "opportunity_dir": str(opportunity_dir),
        "exam": str(exam_path),
        "source_asset_count": len(selected),
        "embedded_image_count": embedded_images,
        "source_integrity_errors": [],
        "generated_visual_substitution": False,
        "human_source_review": "NEEDS_YOU",
        "public_release": "REFUSE",
        "authority_created": False,
    }
    write_json(opportunity_dir / "HOMS_NATIVE_SOURCE_FEDERATION_RECEIPT.json", receipt)
    return receipt


def run_restored_homs_exam(packet: dict[str, Any], execution_dir: Path, *, now: str) -> dict[str, Any]:
    source_booklet = Path(packet["packet_dir"]) / "SOURCES" / "source_pack.md"
    if not source_booklet.is_file():
        raise RuntimeError("HOMS Exam requires the Vesper-custodied customer source booklet")

    projection_dir = execution_dir.parent / "PROJECTION"
    request_path = projection_dir / "HYMARK_NATIVE_EXAM_REQUEST.json"
    base_request = _homs_exam_request(packet, source_booklet)
    selected_assets = _select_topic_bound_assets(base_request)
    manifest = _source_manifest(base_request, selected_assets, source_booklet)
    request = _harden_request(base_request, manifest)
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
        str(ROOT / "scripts" / "run_hymark_exam_builder.py"),
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
        "--subject-profile",
        "history",
        "--grade",
        str(int(request["module_name"].split()[1])),
        "--preferred-language",
        "English",
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
            "HOMS restored native HyMark runtime failed: "
            + (completed.stderr or completed.stdout or "no diagnostic output")[-5000:]
        )

    receipt_paths = sorted(native_root.rglob("HYMARK_EXAM_BUILDER_RECEIPT.json"))
    if len(receipt_paths) != 1:
        raise RuntimeError(f"HOMS restored route expected one native receipt, found {len(receipt_paths)}")
    receipt = json.loads(receipt_paths[0].read_text(encoding="utf-8"))
    outputs = _require_native_outputs(receipt)
    job_dir = Path(str((receipt.get("outputs") or {}).get("job_dir") or ""))
    if not job_dir.is_dir():
        raise RuntimeError("HOMS restored route did not persist its native job directory")
    shutil.copy2(source_booklet, job_dir / "CUSTOMER_SOURCE_BOOKLET.md")

    source_receipts = []
    for opportunity, exam_key in (("1stOpp", "first_exam"), ("2ndOpp", "second_exam")):
        opportunity_dir = job_dir / opportunity
        if not opportunity_dir.is_dir():
            raise RuntimeError(f"HOMS restored route missed {opportunity} assessment pack")
        source_receipts.append(_attach_sources_and_rerender(opportunity_dir, outputs[exam_key], manifest))

    # Recompute hashes after Document Studio source federation may have replaced
    # the learner-facing examination files.
    output_hashes = {name: sha256(path) for name, path in outputs.items()}
    binding = {
        "schema": SCHEMA,
        "incarnation": "HOMS Exam",
        "route": "homs_raw_exam",
        "native_engine": NATIVE_ENGINE_ROUTES["homs_raw_exam"],
        "native_runtime_python": str(native_python),
        "native_runtime_preflight": runtime_preflight,
        "native_receipt_schema": receipt.get("schema"),
        "native_receipt_path": str(receipt_paths[0]),
        "native_job_id": receipt.get("job_id"),
        "native_generation_backend": ((receipt.get("assessor") or {}).get("generation_backend")),
        "native_output_hashes": output_hashes,
        "customer_packet_fingerprint": packet.get("packet_fingerprint"),
        "customer_source_booklet_sha256": sha256(source_booklet),
        "source_federation": manifest,
        "source_federation_receipts": source_receipts,
        "native_capability_preserved": True,
        "source_matrix_and_bank_connected": True,
        "described_missing_visual_allowed": False,
        "invented_source_provenance_allowed": False,
        "surrogate_fallback_allowed": False,
        "surrogate_fallback_used": False,
        "human_review_gate": "NEEDS_YOU",
        "external_release_gate": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    write_json(execution_dir / "HOMS_NATIVE_ROUTE_BINDING.json", binding)
    return {
        "executor": NATIVE_ENGINE_ROUTES["homs_raw_exam"],
        "native_engine_identity": NATIVE_ENGINE_ROUTES["homs_raw_exam"],
        "native_capability_preserved": True,
        "surrogate_fallback_used": False,
        "product_id": "homs_exam",
        "terminal_artifact_kind": "native_hymark_source_federated_exam_and_memoranda_pack",
        "product_pipeline_executed": True,
        "domain_action_executed": False,
        "receipt": binding,
        "native_result": receipt,
    }


__all__ = ["RESTORED_SOURCE_SCHEMA", "run_restored_homs_exam"]

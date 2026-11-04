"""Manifest-bound customer entry points for existing native catalog processors."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from products.professional_evidence_projection import binding_receipt, load_packet, slug, write_json


ROUTES = {
    "DIO AI Assurance": "ai_assurance_raw_projection",
    "Market Radar": "market_radar_raw",
    "Opportunity Foundry": "opportunity_foundry_raw",
    "CPDProof": "vamp_raw_profile",
    "PromotionProof": "vamp_raw_profile",
    "Sophia Integrity": "sophia_raw_integrity",
    "Sophia Research": "sophia_raw_research",
    "Sophia Review": "sophia_raw_review",
    "Sophia Supervisor": "sophia_raw_supervisor",
    "Sophia Tutor": "sophia_raw_tutor",
    "VAMP Performance": "vamp_raw_performance",
    "DIO RegOps": "regops_raw_projection",
    "DossierOps": "dossierops_raw_composition",
    "Offer Lab": "offer_lab_raw",
    "Site Studio": "site_studio_raw_composition",
    "Vesper Desk": "vesper_raw_intake",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_verified_packet(source: Path, target: Path) -> dict[str, Any]:
    packet = load_packet(source)
    target.mkdir(parents=True)
    for row in packet["manifest"].get("files") or []:
        relative = Path(str(row.get("path") or ""))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe customer packet path: {relative}")
        src = (source / relative).resolve()
        dst = target / relative
        if not src.is_file() or _sha(src) != str(row.get("sha256") or ""):
            raise ValueError(f"customer packet source failed hash validation: {relative}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    shutil.copyfile(source / "CUSTOMER_PACKET_MANIFEST.json", target / "CUSTOMER_PACKET_MANIFEST.json")
    copied = load_packet(target)
    if copied["packet_fingerprint"] != packet["packet_fingerprint"]:
        raise ValueError("copied customer packet fingerprint changed")
    return copied


def _attach_dossier_records(packet: dict[str, Any], records_root: Path, packet_root: Path) -> dict[str, Any]:
    records_root = records_root.resolve()
    index = records_root / "DOSSIER_SOURCE_INDEX.csv"
    if not records_root.is_dir() or not index.is_file():
        raise ValueError("DossierOps requires case_records_dir with DOSSIER_SOURCE_INDEX.csv")
    target_root = packet_root / "SOURCES" / "case_records"
    target_root.mkdir(parents=True, exist_ok=True)
    manifest = dict(packet["manifest"])
    declared = {str(row.get("path")) for row in manifest.get("files") or []}
    for path in sorted(records_root.rglob("*")):
        if path.is_symlink():
            raise ValueError("DossierOps case record sources cannot contain symlinks")
        if not path.is_file():
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(records_root):
            raise ValueError("DossierOps case record source escaped its supplied directory")
        relative_inside = path.relative_to(records_root)
        packet_relative = Path("SOURCES") / "case_records" / relative_inside
        if ".." in packet_relative.parts:
            raise ValueError("DossierOps case record path is unsafe")
        destination = packet_root / packet_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        declared.add(packet_relative.as_posix())
    files = []
    for relative in sorted(declared):
        path = packet_root / relative
        if not path.is_file():
            raise ValueError(f"customer packet manifest declared missing source: {relative}")
        files.append({"path": relative, "sha256": _sha(path), "bytes": path.stat().st_size})
    manifest["files"] = files
    manifest.pop("packet_fingerprint", None)
    basis = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    manifest["packet_fingerprint"] = "sha256:" + hashlib.sha256(basis).hexdigest()
    manifest_path = packet_root / "CUSTOMER_PACKET_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return load_packet(packet_root)


def run_native_customer_packet(
    product_name: str, packet: Mapping[str, Any], output_dir: str | Path,
) -> dict[str, Any]:
    route_name = ROUTES.get(product_name)
    if route_name is None:
        raise ValueError(f"no manifest-bound native customer route for {product_name}")
    if packet.get("owner_authorized") is not True:
        raise ValueError("owner_authorized=true is required for customer source processing")
    source_dir = Path(str(packet.get("customer_packet_dir") or "")).expanduser().resolve()
    if not source_dir.is_dir():
        raise ValueError("customer_packet_dir must identify a complete manifest-bound packet directory")
    out = Path(output_dir).resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("customer output directory must be empty")
    out.mkdir(parents=True, exist_ok=True)
    copied_packet = _copy_verified_packet(source_dir, out / "CUSTOMER_PACKET")
    if product_name == "DossierOps":
        records_root = Path(str(packet.get("case_records_dir") or "")).expanduser().resolve()
        copied_packet = _attach_dossier_records(copied_packet, records_root, out / "CUSTOMER_PACKET")
    intake = copied_packet["intake"]
    if intake.get("customer_authorised_processing") is not True:
        raise ValueError("customer packet intake must explicitly authorize source processing")
    if intake.get("external_release_authorised") is not False:
        raise ValueError("customer packet cannot pre-authorize external release")
    if copied_packet["manifest"].get("incarnation") != product_name or intake.get("incarnation") != product_name:
        raise ValueError("customer packet product identity does not match the requested catalog offer")
    routes = json.loads((Path(__file__).resolve().parents[1] / "config/professional_evidence_portfolio/v1/routes.json").read_text(encoding="utf-8"))["routes"]
    route = routes.get(product_name) or {}
    if route.get("route") != route_name or copied_packet["manifest"].get("route", {}).get("route") != route_name:
        raise ValueError("customer packet route does not match the current catalog route")

    from products import professional_evidence_execution as native_routes
    from products import professional_evidence_native as native

    projection = out / "PROJECTION"
    execution = out / "EXECUTION"
    projection.mkdir()
    execution.mkdir()
    write_json(projection / "CUSTOMER_PACKET_BINDING.json", binding_receipt(copied_packet, product_name, route))
    trace_path = projection / "CUSTOMER_FACT_TRACE.json"
    native_routes._trace_customer_records(copied_packet, trace_path)
    operator_id = str(packet.get("operator_id") or "customer-packet-operator")
    now = str(packet.get("as_of") or datetime.now(timezone.utc).replace(microsecond=0).isoformat())

    if product_name == "DIO AI Assurance":
        from products.ai_assurance_customer import run_customer_ai_assurance
        native_result = run_customer_ai_assurance(copied_packet, execution, operator_id=operator_id, now=now)
        terminal = "assurance_evidence_pack"
    elif product_name == "Market Radar":
        from products.market_radar_research import build_targeted_market_brief
        captured = build_targeted_market_brief(copied_packet, execution)
        brief = captured["brief"]
        receipt = {
            "schema": "dio.market_radar.customer_execution.v1",
            "product_id": "market_radar",
            "packet_fingerprint": copied_packet["packet_fingerprint"],
            "source_count": brief.get("source_count", 0),
            "source_failures": brief.get("source_failures", []),
            "market_demand_claimed": False,
            "customer_outreach_performed": False,
            "spend_authorized": False,
            "authority_created": False,
            "external_effects": False,
        }
        write_json(execution / "MARKET_RADAR_CUSTOMER_RECEIPT.json", receipt)
        native_result = {"receipt": receipt}
        terminal = "source_bound_market_brief"
    elif product_name == "Opportunity Foundry":
        native_result = native.run_opportunity_foundry(copied_packet, execution, now=now)
        terminal = "ranked_opportunity_hypotheses"
    elif product_name in {"VAMP Performance", "CPDProof", "PromotionProof"}:
        native_result = native_routes._run_vamp(
            copied_packet, execution, incarnation=product_name,
            operator_id=operator_id, now=now,
        )
        terminal = ({
            "VAMP Performance": "performance_evidence_snapshot",
            "CPDProof": "cpd_evidence_pack",
            "PromotionProof": "promotion_evidence_pack",
        }[product_name])
    elif product_name.startswith("Sophia "):
        requested_telemetry = packet.get("seraph_telemetry_required")
        if requested_telemetry is not None and not isinstance(requested_telemetry, bool):
            raise ValueError("seraph_telemetry_required must be a boolean customer execution option")
        native_result = native_routes._run_sophia(
            copied_packet, execution, incarnation=product_name,
            seraph_telemetry_required=requested_telemetry,
        )
        terminal = str(native_result.get("terminal_artifact_kind") or "held_academic_review_pack")
    elif product_name == "DIO RegOps":
        native_result = native.run_regops(copied_packet, execution, operator_id=operator_id, now=now)
        terminal = "regulatory_operations_readiness_pack"
    elif product_name == "DossierOps":
        native_result = native.run_dossierops(copied_packet, execution, operator_id=operator_id, now=now)
        terminal = "dossier_bundle"
    elif product_name == "Offer Lab":
        native_result = native.run_offer_lab(copied_packet, execution, now=now)
        terminal = "bounded_offer_hypothesis"
    elif product_name == "Site Studio":
        native_result = native_routes._run_site_studio(copied_packet, execution)
        terminal = "static_website_draft_pack"
    else:
        native_result = native_routes._run_vesper(copied_packet, execution)
        terminal = "routed_intake_and_draft_next_step"

    receipt = native_result.get("receipt") or {}
    if product_name.startswith("Sophia "):
        if receipt.get("constitutional_release_authorized") is not False or receipt.get("delivery_released") is not False:
            raise RuntimeError(f"{product_name} native processor did not preserve constitutional and delivery holds")
        seraph_proof = native_result.get("seraph_processing_proof") or {}
        if (seraph_proof.get("schema") != "dio.sophia.seraph_processing_proof.v1"
                or seraph_proof.get("assessment_state") != "HASH_CHAIN_VERIFIED"
                or seraph_proof.get("source_identity_state") != "UNVERIFIED"
                or seraph_proof.get("constitutional_release_authorized") is not False
                or seraph_proof.get("delivery_released") is not False):
            raise RuntimeError(f"{product_name} Seraph processing proof is missing, invalid, or exceeded its boundary")
        receipt = {
            "schema": "dio.sophia.native_customer_boundary.v1",
            "processor_receipt": receipt,
            "seraph_processing_proof": seraph_proof,
            "authority_created": False,
            "external_effects": False,
            "external_release_gate": "REFUSE",
        }
    if receipt.get("authority_created") is not False or receipt.get("external_effects") is not False:
        raise RuntimeError(f"{product_name} native processor crossed its authority/effects boundary")
    for gate in ("external_release_gate", "external_release", "external_publication", "external_send"):
        if gate in receipt and receipt[gate] not in {False, "REFUSE", "HELD"}:
            raise RuntimeError(f"{product_name} native processor unexpectedly authorized {gate}")
    inventory = [
        {"path": str(path.relative_to(out)), "bytes": path.stat().st_size, "sha256": _sha(path)}
        for path in sorted(out.rglob("*")) if path.is_file()
    ]
    package = {
        "schema": "dio.native_customer_packet.execution.v1",
        "product_name": product_name,
        "route": route_name,
        "terminal_artifact_kind": terminal,
        "packet_fingerprint": copied_packet["packet_fingerprint"],
        "source_files": copied_packet["manifest"].get("files") or [],
        "native_receipt": receipt,
        "artifacts": inventory,
        "human_review_required": True,
        "release_authorized": False,
        "external_effects": False,
        "synthetic_acceptance_case": packet.get("synthetic_acceptance_not_customer_evidence") is True,
        "commercial_validation": "UNPROVED",
    }
    package_path = out / "NATIVE_CUSTOMER_PACKET_RECEIPT.json"
    package_path.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return package

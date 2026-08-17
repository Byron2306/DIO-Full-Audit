#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_ROOT = ROOT / "state" / "product_candidates"
DEFAULT_SCHEMA = ROOT / "schemas" / "product_candidate.schema.json"


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def archive_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_zip_json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(archive.read(name).decode("utf-8"))


def first_existing(archive: zipfile.ZipFile, names: list[str]) -> str | None:
    members = set(archive.namelist())
    return next((name for name in names if name in members), None)


def candidate_id(product_id: str, fingerprint: str) -> str:
    raw = f"{product_id}:{fingerprint}"
    return "PC-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16].upper()


def candidate_path(state_root: Path, candidate_id_value: str) -> Path:
    return state_root / candidate_id_value / "PRODUCT_CANDIDATE.json"


def from_phase16_archive(archive_path: Path, state_root: Path = DEFAULT_STATE_ROOT, schema_path: Path = DEFAULT_SCHEMA) -> dict[str, Any]:
    archive_path = archive_path.expanduser().resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(f"Archive not found: {archive_path}")
    with zipfile.ZipFile(archive_path) as archive:
        top_receipt_name = first_existing(archive, ["PRODUCT_INCARNATION_STUDIO_GAUNTLET_RECEIPT.json"])
        incarnation_name = first_existing(archive, ["run-a/INCARNATION_STUDIO_RECEIPT.json"])
        proof_name = first_existing(archive, ["run-a/PROOF_MANIFEST.json"])
        positioning_name = first_existing(archive, ["run-a/strategy/POSITIONING_BRIEF.json"])
        campaign_name = first_existing(archive, ["run-a/strategy/CAMPAIGN_PLAN.json"])
        measurement_name = first_existing(archive, ["run-a/operations/COMMERCIAL_MEASUREMENT_CONTRACT.json"])
        required = {
            "gauntlet_receipt": top_receipt_name,
            "incarnation_receipt": incarnation_name,
            "proof_manifest": proof_name,
            "positioning": positioning_name,
            "campaign": campaign_name,
            "measurement": measurement_name,
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ValueError(f"Phase 16 archive is missing required artifacts: {', '.join(missing)}")
        gauntlet = load_zip_json(archive, top_receipt_name or "")
        incarnation = load_zip_json(archive, incarnation_name or "")
        proof = load_zip_json(archive, proof_name or "")
        positioning = load_zip_json(archive, positioning_name or "")
        campaign = load_zip_json(archive, campaign_name or "")
        measurement = load_zip_json(archive, measurement_name or "")

    product_id = str(incarnation.get("product_id") or gauntlet.get("product_id") or positioning.get("product_id") or "")
    if not product_id:
        raise ValueError("Phase 16 archive does not contain a product id.")
    fingerprint = str(incarnation.get("incarnation_fingerprint") or gauntlet.get("incarnation_fingerprint") or archive_sha256(archive_path))
    cid = candidate_id(product_id, fingerprint)
    output_path = candidate_path(state_root, cid)
    if output_path.exists():
        return read_json(output_path)
    unsupported = list(measurement.get("unsupported_inferences") or [])
    external_validation = bool(positioning.get("external_validation")) or bool(measurement.get("market_validation_claimed"))
    claim_ceiling = "OBSERVED_MARKET" if external_validation else "CONTROLLED_PROOF"
    candidate = {
        "schema": "dio.product_candidate.v1",
        "candidate_id": cid,
        "product_id": product_id,
        "name": str((positioning.get("offer") or {}).get("name") or product_id.replace("_", " ").title()),
        "state": "incarnated",
        "created_at": timestamp(),
        "updated_at": timestamp(),
        "source_signals": [
            {"kind": "phase16_incarnation_archive", "path": str(archive_path), "sha256": archive_sha256(archive_path)},
            {"kind": "positioning_projection", "source_engine": positioning.get("source_engine"), "state": positioning.get("state")},
            {"kind": "campaign_projection", "campaign_id": campaign.get("campaign_id"), "source_engine": campaign.get("source_engine")},
        ],
        "audience": positioning.get("audience") or {},
        "pain": str((positioning.get("audience") or {}).get("pain") or ""),
        "offer": positioning.get("offer") or {},
        "proof": {
            "claim_ceiling": claim_ceiling,
            "manifest_path": proof_name,
            "artifact_count": len(proof.get("artifacts") or []),
            "unsupported_inferences": unsupported,
            "proof_fingerprint": incarnation.get("proof_fingerprint"),
        },
        "incarnation": {
            "receipt_path": top_receipt_name,
            "source_archive": str(archive_path),
            "fingerprint": fingerprint,
            "artifact_integrity": str(gauntlet.get("artifact_integrity") or incarnation.get("artifact_integrity")),
            "human_gate": str(gauntlet.get("human_gate") or incarnation.get("human_gate")),
            "artifact_count": int(incarnation.get("artifact_count") or len(proof.get("artifacts") or [])),
            "external_effects": bool(gauntlet.get("external_effects") or incarnation.get("external_effects")),
        },
        "campaign": {
            "campaign_id": campaign.get("campaign_id"),
            "objective": campaign.get("objective"),
            "channels": campaign.get("channels") or [],
            "publication": campaign.get("publication"),
            "spend_authority": campaign.get("spend_authority"),
            "external_send": campaign.get("external_send"),
            "measurement": campaign.get("measurement") or [],
        },
        "marketfront": {
            "state": "generated_preview",
            "paths": ["run-a/marketfront/index.html", "run-a/marketfront/styles.css", "run-a/marketfront/app.js"],
        },
        "fulfilment_route": {
            "vesper_fulfilment_binding": gauntlet.get("vesper_fulfilment_binding") or incarnation.get("vesper_fulfilment_binding"),
            "evidex_proof_binding": gauntlet.get("evidex_proof_binding") or incarnation.get("evidex_proof_binding"),
            "presence_release_package": gauntlet.get("presence_release_package") or incarnation.get("presence_release_package"),
        },
        "approval": {
            "state": "needs_operator",
            "release_boundary": "External publication, payment, media spend and send authority were refused by the Phase 16 gauntlet.",
            "external_publication": gauntlet.get("external_publication"),
            "external_send": gauntlet.get("external_send"),
            "payment": gauntlet.get("payment"),
            "media_spend": gauntlet.get("media_spend"),
        },
        "commercial_metrics": {
            "market_validation_claimed": bool(measurement.get("market_validation_claimed")),
            "revenue_claimed": bool(measurement.get("revenue_claimed")),
            "events": measurement.get("events") or [],
        },
        "decision": {
            "state": "candidate",
            "reason": "Phase 16 proves governed product incarnation. Live market demand, payment and repeatability are not yet proven for this candidate.",
        },
    }
    jsonschema.validate(candidate, read_json(schema_path), format_checker=jsonschema.FormatChecker())
    write_json(output_path, candidate)
    output_path.chmod(0o600)
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description="Register DIO product candidates from governed incarnation evidence.")
    parser.add_argument("--phase16-archive", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    args = parser.parse_args()
    candidate = from_phase16_archive(args.phase16_archive, args.state_root)
    print(json.dumps({"candidate_id": candidate["candidate_id"], "product_id": candidate["product_id"], "state": candidate["state"], "path": str(candidate_path(args.state_root, candidate["candidate_id"]))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

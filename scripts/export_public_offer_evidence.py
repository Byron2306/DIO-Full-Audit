#!/usr/bin/env python3
"""Export public-safe, honest evidence statements for the canonical offer catalogue."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from presence_core.product_binding_registry import build_phase8_binding_registry


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _source_commit(root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNAVAILABLE"


def _offer(binding: dict[str, Any]) -> dict[str, Any]:
    contract = binding["offer_contract"]
    deliverable = contract["deliverables"][0]
    route = contract["proof"]["route_execution_proof"]
    product_proof = contract["proof"]["product_artifact_proof"]
    return {
        "product_id": contract["product_id"],
        "product_name": contract["product_name"],
        "suite": binding["suite"],
        "buyer_job": contract["problem"]["statement"],
        "bounded_outcome": contract["promised_outcome"]["statement"],
        "primary_deliverable": deliverable["artifact_family"],
        "acceptance_criteria": deliverable["acceptance_criteria"],
        "route_proof": {
            "label": "Route-family execution proof",
            "state": route["state"],
            "scope": route["scope"],
        },
        "named_product_proof": {
            "label": "Named-product customer artifact proof",
            "state": product_proof["state"],
            "scope": product_proof["scope"],
            "available": product_proof["state"] not in {"UNPROVED", "UNAVAILABLE"},
        },
        "market_validation": contract["proof"]["commercial_validation"],
        "cta": {
            "label": contract["cta"]["label"],
            "action": contract["cta"]["action"],
            "href": "/vesper-intake.html?product=" + contract["product_id"],
        },
    }


def export_public_offer_evidence(offer_contracts: Path, proof_registry: Path, output: Path) -> dict[str, Any]:
    """Build a deterministic public projection; path arguments identify the canonical source root."""
    root = Path(offer_contracts).resolve()
    if not root.is_dir() or Path(proof_registry).resolve() != root:
        raise ValueError("Public evidence export requires the same canonical repository root for contracts and proof registry.")
    registry = build_phase8_binding_registry(root)
    offers = sorted((_offer(dict(binding)) for binding in registry["bindings"]), key=lambda row: row["product_name"].casefold())
    if len(offers) != 68 or len({row["product_id"] for row in offers}) != 68:
        raise ValueError("Canonical public evidence export requires exactly 68 unique offers.")
    base = {"schema": "dio.public_offer_evidence.v1", "source_commit": _source_commit(root), "offer_count": len(offers), "offers": offers}
    digest = hashlib.sha256(_canonical(base)).hexdigest()
    payload = {**base, "artifact_id": f"PUBLIC-OFFER-EVIDENCE-{digest[:16].upper()}", "artifact_sha256": digest}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return {"schema": "dio.public_offer_evidence_export_receipt.v1", "offer_count": len(offers), "artifact_id": payload["artifact_id"], "artifact_sha256": digest, "output": str(output)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export_public_offer_evidence(args.root, args.root, args.out), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

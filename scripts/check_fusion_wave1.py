#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check DIO Fusion Wave 1 contract coverage.")
    parser.add_argument("--workspace", default="/home/byron/DIO")
    parser.add_argument("--core", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--out")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    core = Path(args.core).expanduser().resolve()
    out = Path(args.out).expanduser().resolve() if args.out else workspace / "receipts" / "fusion-wave1-latest.json"

    blockers: list[dict[str, str]] = []
    incarnation_path = workspace / "receipts" / "incarnation-latest.json"
    if not incarnation_path.is_file():
        blockers.append({"code": "INCARNATION_RECEIPT_MISSING", "message": str(incarnation_path)})
        incarnation = {}
    else:
        incarnation = _load(incarnation_path)
        if incarnation.get("state") != "READY_FOR_FUSION":
            blockers.append({"code": "INCARNATION_NOT_READY", "message": str(incarnation.get("state"))})

    registry = _load(core / "config" / "dio_fusion_registry.json")
    bindings = _load(core / "config" / "dio_fusion_bindings.json")
    binding_schema = _load(core / "schemas" / "dio_fusion_bindings.schema.json")
    assertion_schema = _load(core / "schemas" / "dio_fusion_assertion.schema.json")
    Draft202012Validator(binding_schema).validate(bindings)
    Draft202012Validator.check_schema(assertion_schema)

    mandatory = {row["system_id"] for row in registry["systems"] if row["must_participate_before_deification"]}
    bound = set(bindings["bindings"])
    if mandatory != bound:
        blockers.append({
            "code": "FUSION_BINDING_COVERAGE_MISMATCH",
            "message": f"missing={sorted(mandatory-bound)} extra={sorted(bound-mandatory)}",
        })

    receipt = {
        "schema": "dio.fusion_wave1.receipt.v1",
        "state": "FUSION_WAVE1_READY" if not blockers else "BLOCKED",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "phase0_snapshot_id": incarnation.get("phase0_snapshot_id"),
        "incarnation_receipt": str(incarnation_path),
        "mandatory_system_count": len(mandatory),
        "bound_system_count": len(bound),
        "canonical_primitives": bindings["primitives"],
        "laws": bindings["laws"],
        "registry_sha256": _sha(registry),
        "bindings_sha256": _sha(bindings),
        "blockers": blockers,
    }
    receipt["receipt_sha256"] = _sha(receipt)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"state": receipt["state"], "systems": len(bound), "blockers": blockers, "receipt": str(out)}, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())

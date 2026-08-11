#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_BEFORE_DEIFICATION = {
    "dio_core",
    "vesper_presence",
    "sophia_integritas",
    "valinor",
    "beast",
    "metatron",
    "arda",
    "seraph",
    "phoenix",
    "evidex",
    "vamp",
    "homs",
    "outlook_triage",
    "microsoft_graph",
    "nichefoundry",
    "document_studio",
    "lingua",
    "format_core",
    "legalis",
    "market_command",
    "commerce_autorelease",
    "dio_product_platform",
    "dio_workflows_site",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def check(workspace: Path, core: Path) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    checks: list[dict[str, Any]] = []

    snapshot_path = workspace / "state" / "system_snapshots" / "latest.json"
    if not snapshot_path.is_file():
        blockers.append({"code": "PHASE0_RECEIPT_MISSING", "message": f"Missing Phase 0 snapshot: {snapshot_path}"})
        snapshot = None
    else:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        ready = snapshot.get("overall_state") == "READY" and not snapshot.get("blockers")
        checks.append({"check": "phase0_ready", "passed": ready, "snapshot_id": snapshot.get("snapshot_id")})
        if not ready:
            blockers.append({"code": "PHASE0_NOT_READY", "message": "Latest Phase 0 snapshot has not earned READY."})

    registry_path = core / "config" / "dio_fusion_registry.json"
    if not registry_path.is_file():
        blockers.append({"code": "FUSION_REGISTRY_MISSING", "message": f"Missing fusion registry: {registry_path}"})
        registry = None
    else:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        systems = {str(row.get("system_id")): row for row in registry.get("systems") or []}
        mandatory = {key for key, row in systems.items() if row.get("must_participate_before_deification") is True}
        complete = mandatory == REQUIRED_BEFORE_DEIFICATION
        checks.append(
            {
                "check": "fusion_inventory_complete",
                "passed": complete,
                "mandatory_system_count": len(mandatory),
                "missing": sorted(REQUIRED_BEFORE_DEIFICATION - mandatory),
                "unexpected_mandatory": sorted(mandatory - REQUIRED_BEFORE_DEIFICATION),
            }
        )
        if not complete:
            blockers.append({"code": "FUSION_INVENTORY_INCOMPLETE", "message": "Mandatory fusion inventory does not match the Incarnation contract."})

        unsafe = [
            key
            for key in mandatory
            if not systems[key].get("authority_boundary") or not systems[key].get("sources")
        ]
        checks.append({"check": "mandatory_authority_boundaries", "passed": not unsafe, "violations": sorted(unsafe)})
        if unsafe:
            blockers.append({"code": "AUTHORITY_BOUNDARY_MISSING", "message": "Mandatory fusion systems lack source or authority boundaries: " + ", ".join(sorted(unsafe))})

    presence_cfg = core / "config" / "presence.json"
    authority_path = core / "presence_core" / "authority.py"
    engine_path = core / "presence_core" / "engine.py"
    llm_path = core / "presence_core" / "llm.py"
    if all(path.is_file() for path in (presence_cfg, authority_path, engine_path, llm_path)):
        cfg = json.loads(presence_cfg.read_text(encoding="utf-8"))
        vesper_ok = (
            (cfg.get("identity") or {}).get("name") == "Vesper"
            and (cfg.get("identity") or {}).get("role") == "DIO Presence Core"
            and (cfg.get("identity") or {}).get("legacy_alias") == "Lilith"
            and (cfg.get("external_replies") or {}).get("default_enabled") is False
            and (cfg.get("external_replies") or {}).get("receipt_required") is True
            and "DIO_PRESENCE_CORE_TELEGRAM_REPLIES\", \"0\"" in authority_path.read_text(encoding="utf-8")
            and "I’m Vesper, DIO’s Presence Core." in engine_path.read_text(encoding="utf-8")
            and "You are Vesper, DIO's Presence Core." in llm_path.read_text(encoding="utf-8")
        )
    else:
        vesper_ok = False
    checks.append({"check": "vesper_canonical_fail_closed", "passed": vesper_ok})
    if not vesper_ok:
        blockers.append({"code": "VESPER_NOT_CANONICAL", "message": "Vesper Presence identity or fail-closed reply authority is incomplete."})

    seraph_path = core / "adapters" / "seraph" / "challenge.py"
    seraph_schema = core / "schemas" / "dio_seraph_challenge.schema.json"
    seraph_ok = seraph_path.is_file() and seraph_schema.is_file()
    if seraph_ok:
        text = seraph_path.read_text(encoding="utf-8")
        seraph_ok = all(
            marker in text
            for marker in (
                "INSUFFICIENT_EVIDENCE",
                "execution_authorized\": False",
                "kernel_authority\": \"Valinor\"",
                "response_action_executed\": False",
            )
        )
    checks.append({"check": "seraph_challenge_contract", "passed": seraph_ok})
    if not seraph_ok:
        blockers.append({"code": "SERAPH_CHALLENGE_CONTRACT_MISSING", "message": "Seraph challenge contract is absent or violates the no-execution boundary."})

    outlook_ok = False
    if registry:
        outlook = next((row for row in registry.get("systems") or [] if row.get("system_id") == "outlook_triage"), None)
        if outlook:
            bounded = " ".join(outlook.get("bounded") or []).lower()
            boundary = str(outlook.get("authority_boundary") or "").lower()
            outlook_ok = all(term in bounded for term in ("send", "reply", "form filling")) and "human approval" in boundary and "valinor" in boundary
    checks.append({"check": "outlook_side_effects_bounded", "passed": outlook_ok})
    if not outlook_ok:
        blockers.append({"code": "OUTLOOK_EXECUTOR_BOUNDARY_MISSING", "message": "Outlook browser/mail side effects are not explicitly human + Valinor gated."})

    created_at = _now()
    receipt = {
        "schema": "dio.incarnation_receipt.v1",
        "created_at": created_at,
        "state": "READY_FOR_FUSION" if not blockers else "BLOCKED",
        "phase0_snapshot_id": snapshot.get("snapshot_id") if snapshot else None,
        "fusion_registry_sha256": _sha(registry) if registry else None,
        "checks": checks,
        "blockers": blockers,
        "law": "Incarnation proves the common case spine, canonical Presence, adversarial challenge contract and complete fusion inventory. It does not itself prove that every specialist executor is locally running or authorize any external action.",
    }
    receipt["receipt_sha256"] = _sha(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Check DIO Incarnation readiness before fusion.")
    parser.add_argument("--workspace", default="/home/byron/DIO")
    parser.add_argument("--core", default=str(ROOT))
    parser.add_argument("--out")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    core = Path(args.core).expanduser().resolve()
    receipt = check(workspace, core)
    out = Path(args.out).expanduser().resolve() if args.out else workspace / "receipts" / "incarnation-latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"state": receipt["state"], "phase0_snapshot_id": receipt["phase0_snapshot_id"], "blockers": receipt["blockers"], "receipt": str(out)}, indent=2))
    return 0 if receipt["state"] == "READY_FOR_FUSION" else 2


if __name__ == "__main__":
    raise SystemExit(main())

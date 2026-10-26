#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
CORE_ROOT = HERE.parents[1]
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from evidence.intelligence import load_source_registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Check DIO Fusion Wave 3 Evidence Intelligence readiness.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--core", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    core = Path(args.core).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    blockers: list[dict[str, str]] = []

    wave2_path = workspace / "receipts" / "fusion-wave2-latest.json"
    if not wave2_path.is_file():
        blockers.append({"code": "FUSION_WAVE2_RECEIPT_MISSING", "message": str(wave2_path)})
        wave2 = {}
    else:
        try:
            wave2 = json.loads(wave2_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            blockers.append({"code": "FUSION_WAVE2_RECEIPT_INVALID", "message": str(exc)})
            wave2 = {}
    if wave2.get("state") != "FUSION_WAVE2_READY":
        blockers.append({"code": "FUSION_WAVE2_NOT_READY", "message": f"Observed state: {wave2.get('state')!r}"})

    try:
        registry = load_source_registry(core / "config" / "dio_evidence_sources.json")
    except Exception as exc:
        blockers.append({"code": "EVIDENCE_SOURCE_REGISTRY_INVALID", "message": f"{type(exc).__name__}: {exc}"})
        registry = {"contributors": {}, "laws": {}}

    try:
        bindings = json.loads((core / "config" / "dio_fusion_bindings.json").read_text(encoding="utf-8"))
    except Exception as exc:
        blockers.append({"code": "FUSION_BINDINGS_INVALID", "message": f"{type(exc).__name__}: {exc}"})
        bindings = {"bindings": {}}

    expected = {
        system_id
        for system_id, primitives in (bindings.get("bindings") or {}).items()
        if {"evidence", "observation"}.intersection(primitives or [])
    }
    observed = set((registry.get("contributors") or {}).keys())
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    if missing:
        blockers.append({"code": "EVIDENCE_CONTRIBUTOR_MISSING", "message": ", ".join(missing)})
    if extra:
        blockers.append({"code": "EVIDENCE_CONTRIBUTOR_NOT_BOUND", "message": ", ".join(extra)})

    laws = registry.get("laws") or {}
    required_laws = {
        "source_lineage_required",
        "support_requires_current_trusted_evidence",
        "contradiction_requires_current_trusted_evidence",
        "evidence_never_creates_execution_authority",
    }
    false_laws = sorted(name for name in required_laws if laws.get(name) is not True)
    if false_laws:
        blockers.append({"code": "EVIDENCE_LAW_DISABLED", "message": ", ".join(false_laws)})

    critical_roles = {
        "sophia_integritas": {"claim_lineage", "authorship_boundary"},
        "beast": {"source_bound_custody"},
        "evidex": {"provenance", "gap_detection"},
        "phoenix": {"negative_evidence", "temporal_persistence"},
        "seraph": {"adversarial_evidence"},
        "homs": {"assessment_evidence"},
        "outlook_triage": {"mail_observation"},
        "microsoft_graph": {"mail_source"},
    }
    contributors = registry.get("contributors") or {}
    for system_id, required_roles in critical_roles.items():
        actual_roles = set((contributors.get(system_id) or {}).get("evidence_roles") or [])
        missing_roles = sorted(required_roles - actual_roles)
        if missing_roles:
            blockers.append({
                "code": "CRITICAL_EVIDENCE_ROLE_MISSING",
                "message": f"{system_id}: {', '.join(missing_roles)}",
            })

    state = "FUSION_WAVE3_READY" if not blockers else "BLOCKED"
    receipt = {
        "schema": "dio.fusion.wave3.receipt.v1",
        "state": state,
        "depends_on": {
            "fusion_wave2_state": wave2.get("state"),
            "fusion_wave2_receipt": str(wave2_path),
        },
        "contributors": len(observed),
        "input_primitives": ["evidence", "observation"],
        "critical_systems": sorted(critical_roles),
        "laws": {
            "source_lineage_required": True,
            "support_requires_current_trusted_evidence": True,
            "contradiction_requires_current_trusted_evidence": True,
            "negative_evidence_preserved": True,
            "custody_explicit": True,
            "evidence_never_creates_execution_authority": True,
        },
        "blockers": blockers,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "state": state,
        "contributors": len(observed),
        "blockers": blockers,
        "receipt": str(out),
    }, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())

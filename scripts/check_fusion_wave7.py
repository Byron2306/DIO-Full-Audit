#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
CORE_ROOT = HERE.parents[1]
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from twin.loki_mirror import LOKI_SOURCE


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DIO Fusion Wave 7 Evidence & Authority Twin readiness.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--core", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    core = Path(args.core).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    blockers: list[dict[str, str]] = []

    wave6_path = workspace / "receipts" / "fusion-wave6-latest.json"
    try:
        wave6 = json.loads(wave6_path.read_text(encoding="utf-8"))
    except Exception as exc:
        blockers.append({"code": "FUSION_WAVE6_RECEIPT_INVALID", "message": str(exc)})
        wave6 = {}
    if wave6.get("state") != "FUSION_WAVE6_READY":
        blockers.append({
            "code": "FUSION_WAVE6_NOT_READY",
            "message": f"Expected FUSION_WAVE6_READY, got {wave6.get('state')!r}.",
        })

    required_core = [
        core / "twin" / "canonical.py",
        core / "twin" / "loki_mirror.py",
        core / "config" / "dio_evidence_authority_twin.json",
        core / "schemas" / "dio_evidence_authority_twin.schema.json",
        core / "tests" / "test_evidence_authority_twin.py",
    ]
    for path in required_core:
        if not path.is_file():
            blockers.append({"code": "TWIN_FILE_MISSING", "message": str(path)})

    try:
        config = json.loads((core / "config" / "dio_evidence_authority_twin.json").read_text(encoding="utf-8"))
    except Exception as exc:
        blockers.append({"code": "TWIN_CONFIG_INVALID", "message": f"{type(exc).__name__}: {exc}"})
        config = {"layers": [], "loki": {}, "laws": {}}

    expected_layers = {
        "world_state",
        "evidence_state",
        "claim_state",
        "requirement_state",
        "authority_state",
        "capability_state",
        "action_state",
        "receipt_state",
    }
    if set(config.get("layers") or []) != expected_layers:
        blockers.append({"code": "TWIN_LAYER_DRIFT", "message": "Evidence & Authority Twin must expose exactly eight canonical layers."})

    loki = config.get("loki") or {}
    if loki.get("source_repository") != LOKI_SOURCE["repository"] or loki.get("source_commit") != LOKI_SOURCE["commit"]:
        blockers.append({"code": "LOKI_SOURCE_DRIFT", "message": "Twin Loki source pin does not match the canonical Metatron source contract."})

    required_laws = {
        "historical_never_silently_current",
        "synthetic_never_canonical",
        "twin_has_no_authority",
        "loki_mirror_has_no_authority",
        "loki_mirror_never_becomes_evidence",
        "loki_mirror_never_executes",
        "valinor_remains_sole_kernel_authority",
        "arda_remains_execution_identity_only",
    }
    disabled = sorted(name for name in required_laws if (config.get("laws") or {}).get(name) is not True)
    if disabled:
        blockers.append({"code": "TWIN_LAW_DISABLED", "message": ",".join(disabled)})

    metatron = workspace / "organs" / "metatron"
    source_specs = {
        "triune_loki": (LOKI_SOURCE["triune_loki"], ("LokiAIService", "challenge_plan")),
        "mirror_maze": (LOKI_SOURCE["mirror_maze"], ("Mystique Mirror World Maze", "MazeTier", "_seraph_synthetic")),
        "deception_router": (LOKI_SOURCE["deception_router"], ("Deception Engine API Router", "get_mystique_maze", "DISINFORMATION")),
    }
    source_fingerprints: dict[str, str] = {}
    mounted_sources = 0
    for source_name, (relative_path, markers) in source_specs.items():
        path = metatron / relative_path
        if not path.is_file():
            blockers.append({"code": "LOKI_MOUNT_SOURCE_MISSING", "message": f"{source_name}: {path}"})
            continue
        mounted_sources += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            blockers.append({"code": "LOKI_MOUNT_SOURCE_UNREADABLE", "message": f"{source_name}: {exc}"})
            continue
        missing = [marker for marker in markers if marker not in text]
        if missing:
            blockers.append({"code": "LOKI_SOURCE_MARKER_DRIFT", "message": f"{source_name}: missing {','.join(missing)}"})
        source_fingerprints[source_name] = _sha256(path)

    mirror_categories = {
        "stale_evidence",
        "claim_contradiction",
        "requirement_regression",
        "authority_expiry",
        "lease_revocation",
        "action_payload_drift",
        "receipt_fork",
        "world_state_drift",
    }

    state = "FUSION_WAVE7_READY" if not blockers else "BLOCKED"
    receipt = {
        "schema": "dio.fusion.wave7.receipt.v1",
        "state": state,
        "depends_on": {
            "fusion_wave6_state": wave6.get("state"),
            "fusion_wave6_receipt": str(wave6_path),
        },
        "twin_layers": len(expected_layers),
        "loki_source_repository": LOKI_SOURCE["repository"],
        "loki_source_commit": LOKI_SOURCE["commit"],
        "loki_mounted_sources": mounted_sources,
        "loki_source_fingerprints": source_fingerprints,
        "mirror_divergence_categories": len(mirror_categories),
        "historical_state_isolation": True,
        "twin_authority": False,
        "loki_mirror_authority": False,
        "loki_mirror_execution": False,
        "kernel_authority": "Valinor",
        "execution_identity_authority": "ARDA",
        "blockers": blockers,
        "receipt": str(out),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if state == "FUSION_WAVE7_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())

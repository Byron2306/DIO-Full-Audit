#!/usr/bin/env python3
"""Generate an approved PCR baseline from a known-good attestation bundle."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_EVIDENCE_BUNDLE = Path("/var/lib/arda/attestation/latest/07_sovereign_attestation.json")
DEFAULT_OUTPUT = Path("/var/lib/arda/attestation/baselines/approved-pcr-baseline.json")
DEFAULT_PCRS = ("0", "1", "7", "11")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _normalize_pcr_map(values: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in (values or {}).items():
        text = str(value or "").strip().lower()
        if text.startswith("0x"):
            text = text[2:]
        if text:
            normalized[str(key)] = text
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an approved ARDA PCR baseline")
    parser.add_argument("--evidence-bundle", default=str(DEFAULT_EVIDENCE_BUNDLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--baseline-name", default="arda-approved-boot")
    parser.add_argument(
        "--pcr",
        dest="pcrs",
        action="append",
        help="PCR index to include. May be repeated. Defaults to 0,1,7,11.",
    )
    args = parser.parse_args()

    evidence_path = Path(args.evidence_bundle).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    evidence = _read_json(evidence_path)

    quote = dict(evidence.get("tpm_pcr_quote") or {})
    identity = dict(evidence.get("tpm_identity") or {})
    software_state_binding = dict(evidence.get("software_state_binding") or {})
    pcr_values = _normalize_pcr_map(quote.get("pcr_values") or {})
    selected_pcrs = tuple(dict.fromkeys(args.pcrs or DEFAULT_PCRS))
    baseline_pcrs = {
        pcr: pcr_values[pcr]
        for pcr in selected_pcrs
        if pcr in pcr_values
    }
    if not baseline_pcrs:
        print("ARDA_PCR_BASELINE: no PCR values were available to baseline", file=sys.stderr)
        return 1

    payload = {
        "schema_version": "arda.phase4.pcr_baseline.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_name": args.baseline_name,
        "source_evidence_bundle": str(evidence_path),
        "node_id": evidence.get("node_id"),
        "mirror_id": evidence.get("mirror_id"),
        "chain_hash": evidence.get("chain_hash"),
        "boot_state": evidence.get("boot_state"),
        "pcr_selection": quote.get("pcr_selection"),
        "pcrs": baseline_pcrs,
        "approved_boot": {
            "manufacturer": identity.get("manufacturer"),
            "identity_chain_mode": identity.get("identity_chain_mode"),
            "manufacturer_rooted": bool(
                identity.get("manufacturer_rooted")
                or (identity.get("ek_certificate_present") and identity.get("ak_certified_by_ek"))
            ),
            "policy_generation": software_state_binding.get("policy_generation"),
            "manifest_id": software_state_binding.get("manifest_id"),
            "generation": software_state_binding.get("generation"),
        },
    }
    _write_json(output_path, payload)
    print(json.dumps({"ok": True, "output": str(output_path), "pcrs": sorted(baseline_pcrs.keys())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.sophia.c10_validation import evaluate_stress_proof  # noqa: E402


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def markdown(payload: dict) -> str:
    lines = [
        "# Sophia C10 Stress Proof Receipt",
        "",
        f"Result: **{payload.get('result')}**",
        f"Meaningful change classes exercised: **{payload.get('meaningful_change_class_count')}**",
        "",
        "## Gates",
        "",
    ]
    for key, value in (payload.get("gates") or {}).items():
        lines.append(f"- {'PASS' if value else 'FAIL'} · `{key}`")
    lines.extend(["", "## Change classes", ""])
    for key, value in (payload.get("change_classes") or {}).items():
        lines.append(f"- {'OBSERVED' if value else 'not observed'} · `{key}`")
    lines.extend([
        "",
        "## Observed",
        "",
        "```json",
        json.dumps(payload.get("observed") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Truth Boundary",
        "",
        str(payload.get("truth_boundary") or ""),
        "",
        f"Stress-proof SHA-256: `{payload.get('stress_proof_sha256')}`",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Judge a Sophia C10 case against the non-trivial stress-proof contract.")
    parser.add_argument("--job-dir", type=Path, required=True)
    args = parser.parse_args()

    job_dir = args.job_dir.expanduser().resolve()
    c10_root = job_dir / "C10_LONGITUDINAL_SPECULUM"
    required = {
        "base_receipt": c10_root / "C10_LIVE_PROOF_RECEIPT.json",
        "longitudinal": c10_root / "LONGITUDINAL_SPECULUM.json",
        "topology": c10_root / "SCHOLARLY_TOPOLOGY_AUDIT.json",
        "queue": c10_root / "SCHOLARLY_DECISION_QUEUE.json",
        "human_validation": c10_root / "C10_HUMAN_VALIDATION.json",
    }
    missing = [str(path) for path in required.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing C10 stress-proof evidence: " + ", ".join(missing))

    payload = evaluate_stress_proof(
        base_receipt=load_json(required["base_receipt"]),
        longitudinal=load_json(required["longitudinal"]),
        topology_audit=load_json(required["topology"]),
        decision_queue=load_json(required["queue"]),
        human_validation=load_json(required["human_validation"]),
    )
    out_json = c10_root / "C10_STRESS_PROOF_RECEIPT.json"
    out_md = c10_root / "C10_STRESS_PROOF_RECEIPT.md"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out_md.write_text(markdown(payload) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0 if payload["stress_proof_passed"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Sophia C10 stress proof blocked: {error}", file=sys.stderr)
        raise SystemExit(2)

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dio.obligations.engine import CAPABILITY_BINDINGS, build
from dio.obligations.models import CANONICAL_STATES, RESERVED_VERDICTS
from products.compiler import load_capability_catalog, load_json


def _read_array(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("evidence_records"), list):
        return payload["evidence_records"]
    raise ValueError("evidence file must be a JSON array or an object with evidence_records")


def inspect_runtime() -> dict:
    catalog, _ = load_capability_catalog(ROOT)
    config = load_json(ROOT / "config" / "portfolio" / "obligation_engine.json")
    return {
        "engine_version": config["engine_version"],
        "provider_id": config["provider_id"],
        "provider_ref": config["provider_ref"],
        "canonical_states": sorted(CANONICAL_STATES),
        "reserved_verdicts": sorted(RESERVED_VERDICTS),
        "human_boundary": "NEEDS_YOU",
        "execution_capable": False,
        "capabilities": {
            capability_id: {
                "status": catalog[capability_id]["status"],
                "provider_ids": [row["provider_id"] for row in catalog[capability_id]["providers"]],
            }
            for capability_id in CAPABILITY_BINDINGS
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or evaluate the DIO Obligation Core v0.1 runtime.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("inspect", help="Show Obligation Core capability and authority boundaries.")

    evaluate_parser = sub.add_parser("evaluate", help="Evaluate one source-bound obligation JSON document.")
    evaluate_parser.add_argument("source", type=Path)
    evaluate_parser.add_argument("--evidence", type=Path, default=None)
    evaluate_parser.add_argument("--now", default=None, help="ISO-8601 evaluation timestamp; useful for reproducible proofs.")

    args = parser.parse_args()
    try:
        if args.command == "inspect":
            print(json.dumps(inspect_runtime(), indent=2, sort_keys=True))
            return 0

        source = load_json(args.source.resolve())
        evidence_records = _read_array(args.evidence.resolve()) if args.evidence else None
        bundle = build(source, evidence_records=evidence_records, now=args.now)
        print(json.dumps(bundle, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"DIO_OBLIGATION_ENGINE_REFUSE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

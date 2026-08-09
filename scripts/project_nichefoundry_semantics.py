#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from commerce.nichefoundry_bridge import commercial_semantic_object_from_nichefoundry  # noqa: E402


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_if_exists(path: Path) -> dict[str, Any]:
    return load_json(path) if path.exists() else {}


def update_receipt(path: Path, cso_path: Path, cso: dict[str, Any]) -> None:
    if not path.exists():
        return
    receipt = load_json(path)
    files = set(receipt.get("files") or [])
    files.add(cso_path.name)
    receipt["files"] = sorted(files)
    receipt["commercial_semantic_object"] = cso_path.name
    receipt["commercial_semantic_object_id"] = cso["object_id"]
    receipt["commercial_semantic_authority"] = cso["authority"]["authority_state"]
    signals = ((cso.get("market_context") or {}).get("signals") or {})
    receipt["commercial_semantic_signal_states"] = {
        state: sum(1 for signal in signals.values() if signal.get("state") == state)
        for state in ("observed", "derived", "unknown")
    }
    write_json(path, receipt)


def project(score_path: Path, campaign_dir: Path, output_path: Path) -> dict[str, Any]:
    score = load_json(score_path)
    campaign = load_if_exists(campaign_dir / "HIVENANCE_HYPOTHESIS.json")
    observation = load_if_exists(campaign_dir / "MARKET_OBSERVATION.json")
    cso = commercial_semantic_object_from_nichefoundry(
        score,
        campaign_record=campaign,
        market_observation=observation,
    )
    write_json(output_path, cso)
    update_receipt(campaign_dir / "MARKETING_INTEGRATION_RECEIPT.json", output_path, cso)
    update_receipt(campaign_dir / "PHASE3_RECEIPT.json", output_path, cso)
    return cso


def main() -> int:
    parser = argparse.ArgumentParser(description="Project a NicheFoundry score receipt into DIO Commercial Semantic Object v1.")
    parser.add_argument("--score", required=True, help="NICHEFOUNDRY_SCORE.json path")
    parser.add_argument("--campaign-dir", help="Campaign directory containing Hivenance/market context")
    parser.add_argument("--out", help="Output CSO path; defaults to COMMERCIAL_SEMANTIC_OBJECT.json beside the score")
    args = parser.parse_args()

    score_path = Path(args.score).expanduser().resolve()
    campaign_dir = Path(args.campaign_dir).expanduser().resolve() if args.campaign_dir else score_path.parent
    output_path = Path(args.out).expanduser().resolve() if args.out else campaign_dir / "COMMERCIAL_SEMANTIC_OBJECT.json"
    cso = project(score_path, campaign_dir, output_path)
    signal_states = {
        state: sum(
            1
            for signal in ((cso.get("market_context") or {}).get("signals") or {}).values()
            if signal.get("state") == state
        )
        for state in ("observed", "derived", "unknown")
    }
    print(json.dumps({
        "object_id": cso["object_id"],
        "authority_state": cso["authority"]["authority_state"],
        "signal_states": signal_states,
        "path": str(output_path),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

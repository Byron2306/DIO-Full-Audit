from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.t19_human_gated_local_release_candidate_gate import (  # noqa: E402
    evaluate_t19_human_gated_local_release_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate whether the source-bound T18 human-gated dry-run marketing proof pack "
            "supports an internal T19 local release-candidate packaging claim."
        )
    )
    parser.add_argument("--t18-marketing-proof-pack", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = evaluate_t19_human_gated_local_release_candidate(
        t18_marketing_proof_pack_path=Path(args.t18_marketing_proof_pack),
        output_path=Path(args.output),
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

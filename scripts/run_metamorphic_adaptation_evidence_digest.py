from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.metamorphic_adaptation_evidence_digest import (
    write_metamorphic_adaptation_evidence_digest,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit final DIO metamorphic adaptation evidence digest."
    )
    parser.add_argument("--full-transfer-digest", required=True)
    parser.add_argument("--real-task-quality-digest", required=True)
    parser.add_argument("--adaptive-evidence-verdict", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    digest = write_metamorphic_adaptation_evidence_digest(
        full_transfer_digest_path=Path(args.full_transfer_digest),
        real_task_quality_digest_path=Path(args.real_task_quality_digest),
        adaptive_evidence_verdict_path=Path(args.adaptive_evidence_verdict),
        output_path=Path(args.output),
    )

    print(json.dumps(asdict(digest), indent=2, sort_keys=True))
    print(digest.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

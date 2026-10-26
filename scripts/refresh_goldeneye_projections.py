#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.commercial_truth_gauntlet import (  # noqa: E402
    ACCEPTANCE_TOKEN as PHASE10_TOKEN,
    run_commercial_truth_gauntlet,
)
from products.control_deck_gauntlet import ACCEPTANCE_TOKEN as PHASE9_TOKEN  # noqa: E402


def refresh() -> tuple[str, str]:
    with tempfile.TemporaryDirectory(prefix="dio-goldeneye-refresh-") as temporary:
        generated = Path(temporary)
        phase10_receipt = run_commercial_truth_gauntlet(output_dir=generated)
        phase9_dir = generated / "control_deck"
        phase9_snapshot_path = phase9_dir / "CONTROL_DECK_PORTFOLIO_SNAPSHOT.json"
        phase10_snapshot_path = generated / "COMMERCIAL_TRUTH_SNAPSHOT.json"
        phase9_snapshot = json.loads(phase9_snapshot_path.read_text(encoding="utf-8"))
        phase10_snapshot = json.loads(phase10_snapshot_path.read_text(encoding="utf-8"))
        if phase10_snapshot.get("control_deck_snapshot_fingerprint") != phase9_snapshot.get("snapshot_fingerprint"):
            raise RuntimeError("Commercial Truth snapshot is not bound to the generated GoldenEye snapshot")

        targets = (
            (phase9_snapshot_path, ROOT / "state/control_deck/CONTROL_DECK_PORTFOLIO_SNAPSHOT.json"),
            (phase9_dir / "CONTROL_DECK_PHASE9_RECEIPT.json", ROOT / "state/control_deck/CONTROL_DECK_PHASE9_RECEIPT.json"),
            (phase10_snapshot_path, ROOT / "state/commercial_truth/COMMERCIAL_TRUTH_SNAPSHOT.json"),
            (generated / "COMMERCIAL_TRUTH_PHASE10_RECEIPT.json", ROOT / "state/commercial_truth/COMMERCIAL_TRUTH_PHASE10_RECEIPT.json"),
        )
        for source, destination in targets:
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, staged_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
            try:
                with os.fdopen(descriptor, "wb") as staged:
                    with source.open("rb") as artifact:
                        shutil.copyfileobj(artifact, staged)
                os.replace(staged_name, destination)
            finally:
                Path(staged_name).unlink(missing_ok=True)

        return phase9_snapshot["snapshot_fingerprint"], phase10_receipt["acceptance_token"]


if __name__ == "__main__":
    fingerprint, token = refresh()
    print(f"{PHASE9_TOKEN}: {fingerprint}")
    print(token)

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from adapters.document_studio.pipeline import ROOT, run_document_studio


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a governed DIO Document Studio request.")
    parser.add_argument("request", type=Path)
    parser.add_argument("--out-root", type=Path, default=ROOT / "deliverables" / "document_studio")
    args = parser.parse_args()
    request_path = args.request.expanduser().resolve()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    output = run_document_studio(request, request_path, args.out_root.expanduser().resolve())
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from homs.core.workflow_engine import WorkflowEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="HOMS - Hybrid Offline Marking System")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run full workflow on a submissions directory")
    run.add_argument("submissions", type=Path, help="Submissions directory")
    run.add_argument("reference_name", type=str, help="Reference name (label)")
    run.add_argument("--reference-path", type=Path, default=Path("data/references/reference.pkl"), help="Path to reference .pkl")
    run.add_argument("--output", type=Path, default=Path("./output"), help="Output directory")
    run.add_argument("--config", type=Path, default=Path("config.json"), help="Config file")

    args = parser.parse_args()

    engine = WorkflowEngine(args.config)
    engine.assessment_agent.load_reference(args.reference_name, args.reference_path)
    engine.run_complete_workflow(args.submissions, args.reference_name, args.output)


if __name__ == "__main__":
    main()

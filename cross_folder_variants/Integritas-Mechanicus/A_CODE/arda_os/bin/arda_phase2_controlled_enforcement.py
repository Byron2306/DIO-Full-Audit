#!/usr/bin/env python3
"""Stage Phase 2 signed policy and controlled enforcement artifacts."""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
DEFAULT_OUTPUT_DIR = REPO_ROOT / "kernel/valinor/releases/phase2"
DEFAULT_POLICY = REPO_ROOT / "arda_policy.json"
DEFAULT_PATHS = (
    "/usr/bin/python3",
    "/usr/bin/sudo",
    "/usr/bin/bash",
    "/usr/bin/systemctl",
    "/usr/bin/ls",
    "/usr/bin/cat",
)


def _run(script_name: str, args: list[str]) -> dict:
    env = dict(os.environ)
    env.setdefault("PYTHONPATH", str(REPO_ROOT))
    result = subprocess.run(
        [PYTHON, str(REPO_ROOT / "bin" / script_name), *args],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = None
    if result.stdout.strip():
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            payload = None
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "payload": payload,
        "raw": (result.stdout + result.stderr).strip(),
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare Phase 2 controlled enforcement artifacts")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--repair-policy-signature", action="store_true")
    parser.add_argument("--enforcement-mode", choices=["audit", "legacy_inode"], default="audit")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = output_dir / "active_bundle.json"
    projection = output_dir / f"projection-{args.enforcement_mode}.json"
    paths = list(dict.fromkeys([*DEFAULT_PATHS, *args.path]))
    steps = []

    if args.repair_policy_signature:
        steps.append({"step": "repair_policy_signature", **_run("arda_sign_policy.py", ["--policy", args.policy, "--verify-after"])})

    steps.append(
        {
            "step": "compile_signed_policy_bundle",
            **_run("arda_compile_policy.py", ["--policy", args.policy, "--output", str(bundle), "--verify-after"]),
        }
    )
    if steps[-1]["ok"]:
        projection_args = [
            "--bundle",
            str(bundle),
            "--output",
            str(projection),
            "--enforcement-mode",
            args.enforcement_mode,
        ]
        for path in paths:
            projection_args.extend(["--path", path])
        steps.append({"step": "compile_projection_plan", **_run("arda_compile_projection.py", projection_args)})

    blockers = [step["step"] for step in steps if not step["ok"]]
    report = {
        "schema_version": "arda.phase2_controlled_enforcement.v1",
        "ok": not blockers,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": str(Path(args.policy).resolve()),
        "output_dir": str(output_dir),
        "bundle": str(bundle),
        "projection_plan": str(projection),
        "enforcement_mode": args.enforcement_mode,
        "seed_paths": paths,
        "blockers": blockers,
        "steps": steps,
        "next_safe_commands": [
            f"sudo install -d -m 0755 /etc/arda/policy",
            f"sudo install -m 0644 {bundle} /etc/arda/policy/active_bundle.json",
            f"sudo install -m 0644 {projection} /etc/arda/policy/active_projection_plan.json",
            "sudo ARDA_SOVEREIGN_MODE=1 ./arda_os/bin/arda policy show --json",
        ]
        if not blockers
        else [],
    }
    _write_json(output_dir / "phase2-readiness.json", report)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("ARDA PHASE 2 CONTROLLED ENFORCEMENT")
        print(f"ok: {report['ok']}")
        print(f"mode: {args.enforcement_mode}")
        print("blockers:")
        for blocker in blockers or ["none"]:
            print(f"- {blocker}")
        if report["next_safe_commands"]:
            print("next_safe_commands:")
            for command in report["next_safe_commands"]:
                print(f"- {command}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

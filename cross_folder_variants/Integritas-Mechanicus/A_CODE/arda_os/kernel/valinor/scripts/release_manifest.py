#!/usr/bin/env python3
"""Create a Valinor kernel release manifest for built artifacts."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _git_head(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a Valinor kernel release manifest")
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source_dir = Path(args.source_dir).resolve()
    artifact_dir = Path(args.artifact_dir).resolve()
    output = Path(args.output).resolve()
    artifacts = []
    for path in sorted(artifact_dir.glob("*.deb")):
        artifacts.append(
            {
                "path": str(path),
                "name": path.name,
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )

    config_path = source_dir / ".config"
    manifest = {
        "schema_version": "arda.valinor_kernel_release.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "kernel_release_at_manifest": platform.release(),
        "source_dir": str(source_dir),
        "source_git_head": _git_head(source_dir),
        "config": {
            "path": str(config_path),
            "present": config_path.is_file(),
            "sha256": _sha256(config_path) if config_path.is_file() else None,
        },
        "artifact_dir": str(artifact_dir),
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(output), "artifact_count": len(artifacts)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

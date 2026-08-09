#!/usr/bin/env python3
"""Verify Valinor release manifest artifact hashes before install planning."""

import argparse
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Valinor kernel release manifest")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = []
    artifacts = []
    for artifact in manifest.get("artifacts", []):
        path = Path(artifact["path"])
        present = path.is_file()
        actual_sha256 = _sha256(path) if present else None
        ok = present and actual_sha256 == artifact.get("sha256")
        if not ok:
            failures.append(artifact.get("name") or str(path))
        artifacts.append(
            {
                "name": artifact.get("name"),
                "path": str(path),
                "present": present,
                "expected_sha256": artifact.get("sha256"),
                "actual_sha256": actual_sha256,
                "ok": ok,
            }
        )

    report = {
        "ok": not failures,
        "manifest": str(manifest_path),
        "schema_version": manifest.get("schema_version"),
        "artifact_count": len(artifacts),
        "failures": failures,
        "artifacts": artifacts,
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("VALINOR RELEASE MANIFEST VERIFY")
        print(f"ok: {report['ok']}")
        print("failures:")
        for failure in failures or ["none"]:
            print(f"- {failure}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

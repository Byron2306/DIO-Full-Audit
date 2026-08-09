#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from zipfile import ZIP_DEFLATED, ZipFile


REPO_ROOT = Path(__file__).resolve().parent.parent


def _now_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _run(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=str(cwd) if cwd else None, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _copy_path(src: Path, dest_root: Path, rel_name: str) -> bool:
    if not src.exists():
        return False
    dest = dest_root / rel_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns(
            "wg0.conf",
            "*.key",
            "*.pem",
            "*.crt",
            "*.cer",
            "*priv*",
            "*secret*",
        ))
    else:
        shutil.copy2(src, dest)
    return True


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _docker_ps() -> list[str]:
    result = _run(["docker", "ps", "--format", "{{.Names}}"])
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _docker_exec_exists(container: str, path: str) -> bool:
    result = _run(["docker", "exec", container, "sh", "-lc", f"test -e {path!r}"])
    return result.returncode == 0


def _docker_cp(container: str, src_path: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = _run(["docker", "cp", f"{container}:{src_path}", str(dest)])
    return result.returncode == 0


def _iter_existing(paths: Iterable[tuple[Path, str]]) -> Iterable[tuple[Path, str]]:
    for src, rel in paths:
        if src.exists():
            yield src, rel


def _safe_rel_name(path: Path) -> str:
    return str(path).lstrip("/").replace("/", "__")


def collect_host_evidence(bundle_root: Path, gha_run_id: str) -> dict[str, bool]:
    copied: dict[str, bool] = {}
    host_paths = [
        (REPO_ROOT / "evidence-bundle", "host/evidence-bundle"),
        (REPO_ROOT / "backend" / "sigma_rules", "host/sigma_rules"),
        (REPO_ROOT / "analytics", "host/analytics"),
        (REPO_ROOT / "artifacts", "host/artifacts"),
        (REPO_ROOT / ".tmp" / f"gha-run-{gha_run_id}", f"host/gha/gha-run-{gha_run_id}"),
        (Path("/tmp") / f"metatron_evidence_bundle_{gha_run_id}", f"host/tmp/metatron_evidence_bundle_{gha_run_id}"),
        (Path("/tmp") / f"metatron_run_{gha_run_id}", f"host/tmp/metatron_run_{gha_run_id}"),
        (Path("/tmp") / f"metatron_run_{gha_run_id}_extracted", f"host/tmp/metatron_run_{gha_run_id}_extracted"),
        (Path("/tmp") / f"metatron_atomic_results_{gha_run_id}", f"host/tmp/metatron_atomic_results_{gha_run_id}"),
        (Path("/tmp") / "gha_all_runs", "host/tmp/gha_all_runs"),
        (Path("/home/byron/Downloads/seraph-evidence-bundle-2026-04-20"), "host/downloads/seraph-evidence-bundle-2026-04-20"),
        (REPO_ROOT / "metatron-evidence-package-real-sandbox-s5-2026-04-18", "host/repo/metatron-evidence-package-real-sandbox-s5-2026-04-18"),
        (REPO_ROOT / "metatron-evidence-package-real-sandbox-2026-04-18", "host/repo/metatron-evidence-package-real-sandbox-2026-04-18"),
    ]
    for src, rel in _iter_existing(host_paths):
        try:
            copied[rel] = _copy_path(src, bundle_root, rel)
        except (PermissionError, shutil.Error):
            copied[rel] = False

    tmp_archives = sorted(Path("/tmp").glob("*.zip")) + sorted(Path("/tmp").glob("*.tar.gz")) + sorted(Path("/tmp").glob("*.tgz"))
    for src in tmp_archives:
        rel = f"host/tmp/archives/{src.name}"
        try:
            copied[rel] = _copy_path(src, bundle_root, rel)
        except (PermissionError, shutil.Error):
            copied[rel] = False

    nested_tmp_archives = sorted(Path("/tmp/gha_all_runs").glob("*.zip")) if Path("/tmp/gha_all_runs").exists() else []
    for src in nested_tmp_archives:
        rel = f"host/tmp/gha_all_runs_archives/{src.name}"
        try:
            copied[rel] = _copy_path(src, bundle_root, rel)
        except (PermissionError, shutil.Error):
            copied[rel] = False
    return copied


def collect_container_evidence(bundle_root: Path, containers: list[str]) -> dict[str, dict[str, object]]:
    summary: dict[str, dict[str, object]] = {}
    known_paths = {
        "seraph-backend": [
            "/app/backend/data",
        ],
        "seraph-zeek": ["/usr/local/zeek/logs"],
        "seraph-suricata": ["/var/log/suricata"],
        "seraph-falco": ["/var/log/falco"],
        "seraph-velociraptor": ["/var/log/velociraptor", "/opt/velociraptor/logs"],
    }

    for container in containers:
        container_dir = bundle_root / "containers" / container
        container_dir.mkdir(parents=True, exist_ok=True)

        logs = _run(["docker", "logs", container])
        _write_text(container_dir / "docker.logs.txt", (logs.stdout or "") + ("\nSTDERR:\n" + logs.stderr if logs.stderr else ""))

        inspect = _run(["docker", "inspect", container])
        if inspect.stdout:
            _write_text(container_dir / "docker.inspect.json", inspect.stdout)

        top = _run(["docker", "top", container, "-eo", "pid,ppid,user,etime,cmd"])
        _write_text(container_dir / "docker.top.txt", (top.stdout or "") + ("\nSTDERR:\n" + top.stderr if top.stderr else ""))

        copied_paths = []
        missing_paths = []
        for path in known_paths.get(container, []):
            if _docker_exec_exists(container, path):
                safe_name = path.lstrip("/").replace("/", "__")
                if _docker_cp(container, path, container_dir / safe_name):
                    copied_paths.append(path)
                else:
                    missing_paths.append(f"{path} (copy failed)")
            else:
                missing_paths.append(path)

        summary[container] = {
            "copied_paths": copied_paths,
            "missing_paths": missing_paths,
        }
    return summary


def write_metadata(bundle_root: Path, gha_run_id: str, promotion_log: Path, host_summary: dict[str, bool], container_summary: dict[str, dict[str, object]]) -> None:
    payload = {
        "schema": "full_evidence_package.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gha_run_id": gha_run_id,
        "promotion_log": str(promotion_log),
        "host_summary": host_summary,
        "container_summary": container_summary,
    }
    _write_text(bundle_root / "manifest.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")


def zip_dir(src_dir: Path, zip_path: Path) -> None:
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(src_dir.rglob("*")):
            if path.is_dir():
                continue
            zf.write(path, arcname=path.relative_to(src_dir))


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect host and container evidence into a zip package.")
    parser.add_argument("--gha-run-id", required=True)
    parser.add_argument("--out-dir", default="downloaded_artifacts")
    parser.add_argument("--promotion-log", default="")
    args = parser.parse_args()

    out_base = (REPO_ROOT / args.out_dir).resolve()
    bundle_root = out_base / f"full_evidence_package_{args.gha_run_id}_{_now_slug()}"
    bundle_root.mkdir(parents=True, exist_ok=True)

    promotion_log = Path(args.promotion_log).resolve() if args.promotion_log else bundle_root / "promotion_report.txt"

    host_summary = collect_host_evidence(bundle_root, args.gha_run_id)
    containers = _docker_ps()
    container_summary = collect_container_evidence(bundle_root, containers)
    write_metadata(bundle_root, args.gha_run_id, promotion_log, host_summary, container_summary)

    zip_path = bundle_root.with_suffix(".zip")
    zip_dir(bundle_root, zip_path)

    print(json.dumps({
        "bundle_root": str(bundle_root),
        "zip_path": str(zip_path),
        "containers": containers,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Refuse Valinor kernel installation plans that are incomplete or unsafe."""

import argparse
import json
import re
from pathlib import Path


PACKAGE_RE = re.compile(r"^(linux-(image|headers)-(?P<version>.+?))_(?P<pkgver>[^_]+)_(?P<arch>[^_]+)\.deb$")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _package_meta(path_text: str) -> dict:
    path = Path(path_text)
    match = PACKAGE_RE.match(path.name)
    meta = {
        "path": str(path),
        "name": path.name,
        "present": path.is_file(),
        "kind": None,
        "kernel_version": None,
        "package_version": None,
        "arch": None,
        "valinor": "valinor" in path.name,
    }
    if match:
        meta.update(
            {
                "kind": match.group(2),
                "kernel_version": match.group("version"),
                "package_version": match.group("pkgver"),
                "arch": match.group("arch"),
            }
        )
    return meta


def _is_debug_package(path_text: str) -> bool:
    name = Path(path_text).name
    return "-dbg_" in name or "-dbgsym_" in name


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Valinor install plan before dpkg")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--install-plan", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    plan_path = Path(args.install_plan).resolve()
    manifest = _load_json(manifest_path)
    plan = _load_json(plan_path)

    image_packages = [
        _package_meta(path)
        for path in plan.get("artifacts", {}).get("linux_image_packages", [])
        if not _is_debug_package(path)
    ]
    header_packages = [_package_meta(path) for path in plan.get("artifacts", {}).get("linux_header_packages", [])]
    all_packages = image_packages + header_packages

    image_versions = {pkg["kernel_version"] for pkg in image_packages if pkg["kernel_version"]}
    header_versions = {pkg["kernel_version"] for pkg in header_packages if pkg["kernel_version"]}
    manifest_artifact_names = {artifact.get("name") for artifact in manifest.get("artifacts", [])}
    plan_artifact_names = {Path(pkg["path"]).name for pkg in all_packages}

    blockers = []
    if manifest.get("schema_version") != "arda.valinor_kernel_release.v1":
        blockers.append("unexpected_manifest_schema")
    if plan.get("schema_version") != "arda.valinor_install_plan.v1":
        blockers.append("unexpected_install_plan_schema")
    if not image_packages:
        blockers.append("missing_linux_image_package")
    if not header_packages:
        blockers.append("missing_linux_headers_package")
    if any(not pkg["present"] for pkg in all_packages):
        blockers.append("missing_package_file")
    if any(not pkg["valinor"] for pkg in all_packages):
        blockers.append("non_valinor_package")
    if len(image_versions) != 1:
        blockers.append("ambiguous_linux_image_version")
    if len(header_versions) != 1:
        blockers.append("ambiguous_linux_headers_version")
    if image_versions and header_versions and image_versions != header_versions:
        blockers.append("image_headers_version_mismatch")
    if not plan_artifact_names.issubset(manifest_artifact_names):
        blockers.append("install_plan_not_backed_by_manifest")
    if plan.get("ok") is not True:
        blockers.append("install_plan_not_ok")

    report = {
        "ok": not blockers,
        "blockers": blockers,
        "manifest": str(manifest_path),
        "install_plan": str(plan_path),
        "kernel_versions": {
            "images": sorted(version for version in image_versions if version),
            "headers": sorted(version for version in header_versions if version),
        },
        "packages": {
            "images": image_packages,
            "headers": header_packages,
        },
        "next_step": "sudo dpkg -i <headers.deb> <image.deb>" if not blockers else None,
    }

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("VALINOR PREINSTALL GATE")
        print(f"ok: {report['ok']}")
        print("blockers:")
        for blocker in blockers or ["none"]:
            print(f"- {blocker}")
        if report["next_step"]:
            print(f"next_step: {report['next_step']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

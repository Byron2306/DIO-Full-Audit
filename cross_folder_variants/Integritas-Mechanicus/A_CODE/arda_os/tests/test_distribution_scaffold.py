import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(script: str, *args: str) -> dict:
    completed = subprocess.run(
        [sys.executable, script, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


def _run_raw(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, script, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_prepare_overlay_builds_expected_tree(tmp_path):
    payload = _run(
        "arda_os/distribution/scripts/prepare_arda_overlay.py",
        "--output-root",
        str(tmp_path / "overlay"),
    )

    overlay_root = Path(payload["overlay_root"])
    assert payload["ok"] is True
    assert (overlay_root / "etc/systemd/system/arda-phase4-remote-verifier.service").is_file()
    assert (overlay_root / "etc/arda/arda-verifier.env").is_file()
    assert (overlay_root / "usr/share/arda/identity/arda-wallpaper.png").is_file()


def test_render_distribution_manifest_outputs_files(tmp_path):
    manifest_path = tmp_path / "distribution-manifest.json"
    installer_path = tmp_path / "installer-profile.json"
    payload = _run(
        "arda_os/distribution/scripts/render_distribution_manifest.py",
        "--manifest-output",
        str(manifest_path),
        "--installer-profile-output",
        str(installer_path),
    )

    assert payload["ok"] is True
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    installer = json.loads(installer_path.read_text(encoding="utf-8"))
    assert manifest["distribution_id"] == "arda-valinor"
    assert "valinor_release" in manifest
    assert "voice_profiles" in manifest
    assert "harmony_discovery" in manifest
    assert installer["secure_boot"]["required"] is True


def test_render_iso_plan_emits_distribution_phases(tmp_path):
    output = tmp_path / "iso-plan.json"
    payload = _run(
        "arda_os/distribution/scripts/render_iso_plan.py",
        "--output",
        str(output),
    )

    assert payload["ok"] is True
    plan = json.loads(output.read_text(encoding="utf-8"))
    assert plan["distribution_id"] == "arda-valinor"
    assert len(plan["phases"]) >= 5


def test_render_rootfs_plan_emits_debootstrap_flow(tmp_path):
    output = tmp_path / "rootfs-plan.json"
    payload = _run(
        "arda_os/distribution/scripts/render_rootfs_plan.py",
        "--output",
        str(output),
    )

    assert payload["ok"] is True
    plan = json.loads(output.read_text(encoding="utf-8"))
    assert plan["distribution_id"] == "arda-valinor"
    assert plan["debootstrap"]["series"] == "trixie"
    assert "required_packages" in plan["package_installation"]
    assert "live-boot" in plan["package_installation"]["required_packages"]
    assert "live-media-path=/live" in plan["live_build"]["bootappend_live"]


def test_apply_overlay_copies_generated_rootfs(tmp_path):
    overlay_output = _run(
        "arda_os/distribution/scripts/prepare_arda_overlay.py",
        "--output-root",
        str(tmp_path / "overlay-build"),
    )
    overlay_root = Path(overlay_output["overlay_root"])
    rootfs_dir = tmp_path / "rootfs"
    payload = _run(
        "arda_os/distribution/scripts/apply_overlay.py",
        "--overlay-root",
        str(overlay_root),
        "--rootfs-dir",
        str(rootfs_dir),
    )

    assert payload["ok"] is True
    assert (rootfs_dir / "etc/systemd/system/arda-phase4-remote-verifier.service").is_file()
    assert (rootfs_dir / "opt/arda/arda_os/bin/arda").is_file()


def test_assemble_image_workspace_stages_kernel_and_plans(tmp_path):
    overlay_output = _run(
        "arda_os/distribution/scripts/prepare_arda_overlay.py",
        "--output-root",
        str(tmp_path / "overlay-build"),
    )
    manifest_output = _run(
        "arda_os/distribution/scripts/render_distribution_manifest.py",
        "--manifest-output",
        str(tmp_path / "distribution-manifest.json"),
        "--installer-profile-output",
        str(tmp_path / "installer-profile.json"),
    )
    _run(
        "arda_os/distribution/scripts/render_rootfs_plan.py",
        "--output",
        str(tmp_path / "rootfs-plan.json"),
    )
    payload = _run(
        "arda_os/distribution/scripts/assemble_image_workspace.py",
        "--rootfs-plan",
        str(tmp_path / "rootfs-plan.json"),
        "--overlay-root",
        str(Path(overlay_output["overlay_root"])),
        "--distribution-manifest",
        str(tmp_path / "distribution-manifest.json"),
        "--workspace-root",
        str(tmp_path / "workspace"),
    )

    assert payload["ok"] is True
    summary = json.loads((tmp_path / "workspace" / "plans" / "workspace-summary.json").read_text(encoding="utf-8"))
    assert summary["kernel_artifacts"]
    assert "debootstrap" in summary["build_commands"]
    assert "generate_initramfs" in summary["build_commands"]
    assert (tmp_path / "workspace" / "overlay-rootfs").is_dir()


def test_run_image_workspace_dry_run_reports_missing_commands(tmp_path):
    overlay_output = _run(
        "arda_os/distribution/scripts/prepare_arda_overlay.py",
        "--output-root",
        str(tmp_path / "overlay-build"),
    )
    _run(
        "arda_os/distribution/scripts/render_distribution_manifest.py",
        "--manifest-output",
        str(tmp_path / "distribution-manifest.json"),
        "--installer-profile-output",
        str(tmp_path / "installer-profile.json"),
    )
    _run(
        "arda_os/distribution/scripts/render_rootfs_plan.py",
        "--output",
        str(tmp_path / "rootfs-plan.json"),
    )
    _run(
        "arda_os/distribution/scripts/assemble_image_workspace.py",
        "--rootfs-plan",
        str(tmp_path / "rootfs-plan.json"),
        "--overlay-root",
        str(Path(overlay_output["overlay_root"])),
        "--distribution-manifest",
        str(tmp_path / "distribution-manifest.json"),
        "--workspace-root",
        str(tmp_path / "workspace"),
    )
    payload = _run(
        "arda_os/distribution/scripts/run_image_workspace.py",
        "--summary",
        str(tmp_path / "workspace" / "plans" / "workspace-summary.json"),
        "--output",
        str(tmp_path / "workspace-run-report.json"),
    )

    assert payload["execute"] is False
    assert payload["selected_order"][0] == "debootstrap"
    assert "generate_initramfs" in payload["selected_order"]
    assert payload["steps"]


def test_export_image_workspace_shell_renders_script(tmp_path):
    overlay_output = _run(
        "arda_os/distribution/scripts/prepare_arda_overlay.py",
        "--output-root",
        str(tmp_path / "overlay-build"),
    )
    _run(
        "arda_os/distribution/scripts/render_distribution_manifest.py",
        "--manifest-output",
        str(tmp_path / "distribution-manifest.json"),
        "--installer-profile-output",
        str(tmp_path / "installer-profile.json"),
    )
    _run(
        "arda_os/distribution/scripts/render_rootfs_plan.py",
        "--output",
        str(tmp_path / "rootfs-plan.json"),
    )
    _run(
        "arda_os/distribution/scripts/assemble_image_workspace.py",
        "--rootfs-plan",
        str(tmp_path / "rootfs-plan.json"),
        "--overlay-root",
        str(Path(overlay_output["overlay_root"])),
        "--distribution-manifest",
        str(tmp_path / "distribution-manifest.json"),
        "--workspace-root",
        str(tmp_path / "workspace"),
    )
    payload = _run(
        "arda_os/distribution/scripts/export_image_workspace_shell.py",
        "--summary",
        str(tmp_path / "workspace" / "plans" / "workspace-summary.json"),
        "--output",
        str(tmp_path / "run-workspace.sh"),
    )

    assert payload["ok"] is True
    script = (tmp_path / "run-workspace.sh").read_text(encoding="utf-8")
    assert "debootstrap" in script
    assert "workspace-artifacts" in script


def test_render_image_artifact_plan_emits_iso_and_disk_outputs(tmp_path):
    rootfs_plan = tmp_path / "rootfs-plan.json"
    _run(
        "arda_os/distribution/scripts/render_rootfs_plan.py",
        "--output",
        str(rootfs_plan),
    )
    output = tmp_path / "image-artifact-plan.json"
    payload = _run(
        "arda_os/distribution/scripts/render_image_artifact_plan.py",
        "--rootfs-plan",
        str(rootfs_plan),
        "--output",
        str(output),
    )

    assert payload["ok"] is True
    plan = json.loads(output.read_text(encoding="utf-8"))
    artifact_ids = [artifact["id"] for artifact in plan["artifact_formats"]]
    assert "raw_disk" in artifact_ids
    assert "live_iso" in artifact_ids
    assert "installer_iso" in artifact_ids


def test_render_installer_recipe_captures_first_boot_contract(tmp_path):
    manifest_path = tmp_path / "distribution-manifest.json"
    installer_profile_path = tmp_path / "installer-profile.json"
    _run(
        "arda_os/distribution/scripts/render_distribution_manifest.py",
        "--manifest-output",
        str(manifest_path),
        "--installer-profile-output",
        str(installer_profile_path),
    )
    output = tmp_path / "installer-recipe.json"
    payload = _run(
        "arda_os/distribution/scripts/render_installer_recipe.py",
        "--distribution-manifest",
        str(manifest_path),
        "--output",
        str(output),
    )

    assert payload["ok"] is True
    recipe = json.loads(output.read_text(encoding="utf-8"))
    assert recipe["first_boot_contract"]["remote_verifier_required"] is True
    assert recipe["partition_recipe"]["esp"]["filesystem"] == "fat32"


def test_render_release_bundle_links_distribution_plans(tmp_path):
    manifest_path = tmp_path / "distribution-manifest.json"
    installer_profile_path = tmp_path / "installer-profile.json"
    rootfs_plan = tmp_path / "rootfs-plan.json"
    image_plan = tmp_path / "image-artifact-plan.json"
    installer_recipe = tmp_path / "installer-recipe.json"
    release_bundle = tmp_path / "release-bundle.json"

    _run(
        "arda_os/distribution/scripts/render_distribution_manifest.py",
        "--manifest-output",
        str(manifest_path),
        "--installer-profile-output",
        str(installer_profile_path),
    )
    _run(
        "arda_os/distribution/scripts/render_rootfs_plan.py",
        "--output",
        str(rootfs_plan),
    )
    _run(
        "arda_os/distribution/scripts/render_image_artifact_plan.py",
        "--rootfs-plan",
        str(rootfs_plan),
        "--output",
        str(image_plan),
    )
    _run(
        "arda_os/distribution/scripts/render_installer_recipe.py",
        "--distribution-manifest",
        str(manifest_path),
        "--output",
        str(installer_recipe),
    )
    payload = _run(
        "arda_os/distribution/scripts/render_release_bundle.py",
        "--distribution-manifest",
        str(manifest_path),
        "--image-plan",
        str(image_plan),
        "--installer-recipe",
        str(installer_recipe),
        "--output",
        str(release_bundle),
    )

    assert payload["ok"] is True
    bundle = json.loads(release_bundle.read_text(encoding="utf-8"))
    assert bundle["distribution_id"] == "arda-valinor"
    assert "live-iso" in bundle["release_channels"]
    assert bundle["boot_contract"]["os_grade_prefers_signed_verdict"] is True


def test_assemble_artifact_workspace_stages_release_targets(tmp_path):
    overlay_output = _run(
        "arda_os/distribution/scripts/prepare_arda_overlay.py",
        "--output-root",
        str(tmp_path / "overlay-build"),
    )
    _run(
        "arda_os/distribution/scripts/render_distribution_manifest.py",
        "--manifest-output",
        str(tmp_path / "distribution-manifest.json"),
        "--installer-profile-output",
        str(tmp_path / "installer-profile.json"),
    )
    _run(
        "arda_os/distribution/scripts/render_rootfs_plan.py",
        "--output",
        str(tmp_path / "rootfs-plan.json"),
    )
    _run(
        "arda_os/distribution/scripts/assemble_image_workspace.py",
        "--rootfs-plan",
        str(tmp_path / "rootfs-plan.json"),
        "--overlay-root",
        str(Path(overlay_output["overlay_root"])),
        "--distribution-manifest",
        str(tmp_path / "distribution-manifest.json"),
        "--workspace-root",
        str(tmp_path / "workspace"),
    )
    _run(
        "arda_os/distribution/scripts/render_image_artifact_plan.py",
        "--rootfs-plan",
        str(tmp_path / "rootfs-plan.json"),
        "--output",
        str(tmp_path / "image-artifact-plan.json"),
    )
    payload = _run(
        "arda_os/distribution/scripts/assemble_artifact_workspace.py",
        "--image-plan",
        str(tmp_path / "image-artifact-plan.json"),
        "--workspace-summary",
        str(tmp_path / "workspace" / "plans" / "workspace-summary.json"),
        "--output-root",
        str(tmp_path / "artifact-workspace"),
    )

    assert payload["ok"] is True
    summary = json.loads(
        (tmp_path / "artifact-workspace" / "plans" / "artifact-workspace-summary.json").read_text(encoding="utf-8")
    )
    assert "raw_disk" in summary["artifact_outputs"]
    assert "emit_live_iso" in summary["build_commands"]
    assert "make_live_rootfs" in summary["build_commands"]
    assert summary["build_commands"]["make_live_rootfs"][0] == "/usr/bin/mksquashfs"
    assert summary["build_commands"]["make_esp_image"][0:2] == ["bash", "-lc"]
    assert "mkfs.vfat" in summary["build_commands"]["make_esp_image"][2]
    assert "mcopy" in summary["build_commands"]["make_esp_image"][2]
    emit_live_iso = " ".join(summary["build_commands"]["emit_live_iso"])
    assert "-append_partition" in emit_live_iso
    assert " -e esp.img " in f" {emit_live_iso} "
    assert (tmp_path / "artifact-workspace" / "release").is_dir()
    assert summary["rootfs_ready"] is False
    assert "rootfs_snapshot_empty" in summary["blockers"]


def test_assemble_artifact_workspace_skips_special_files_in_rootfs(tmp_path):
    overlay_output = _run(
        "arda_os/distribution/scripts/prepare_arda_overlay.py",
        "--output-root",
        str(tmp_path / "overlay-build"),
    )
    _run(
        "arda_os/distribution/scripts/render_distribution_manifest.py",
        "--manifest-output",
        str(tmp_path / "distribution-manifest.json"),
        "--installer-profile-output",
        str(tmp_path / "installer-profile.json"),
    )
    _run(
        "arda_os/distribution/scripts/render_rootfs_plan.py",
        "--output",
        str(tmp_path / "rootfs-plan.json"),
    )
    _run(
        "arda_os/distribution/scripts/assemble_image_workspace.py",
        "--rootfs-plan",
        str(tmp_path / "rootfs-plan.json"),
        "--overlay-root",
        str(Path(overlay_output["overlay_root"])),
        "--distribution-manifest",
        str(tmp_path / "distribution-manifest.json"),
        "--workspace-root",
        str(tmp_path / "workspace"),
    )
    rootfs_dir = tmp_path / "workspace" / "rootfs"
    (rootfs_dir / "etc").mkdir(parents=True, exist_ok=True)
    (rootfs_dir / "etc" / "regular.txt").write_text("arda\n", encoding="utf-8")
    os.symlink("regular.txt", rootfs_dir / "etc" / "linked.txt")
    os.mkfifo(rootfs_dir / "etc" / "skip-me.fifo")
    _run(
        "arda_os/distribution/scripts/render_image_artifact_plan.py",
        "--rootfs-plan",
        str(tmp_path / "rootfs-plan.json"),
        "--output",
        str(tmp_path / "image-artifact-plan.json"),
    )

    _run(
        "arda_os/distribution/scripts/assemble_artifact_workspace.py",
        "--image-plan",
        str(tmp_path / "image-artifact-plan.json"),
        "--workspace-summary",
        str(tmp_path / "workspace" / "plans" / "workspace-summary.json"),
        "--output-root",
        str(tmp_path / "artifact-workspace"),
    )

    snapshot_etc = tmp_path / "artifact-workspace" / "rootfs-snapshot" / "etc"
    assert (snapshot_etc / "regular.txt").is_file()
    assert (snapshot_etc / "linked.txt").is_symlink()
    assert not (snapshot_etc / "skip-me.fifo").exists()


def test_export_artifact_workspace_shell_renders_emission_steps(tmp_path):
    overlay_output = _run(
        "arda_os/distribution/scripts/prepare_arda_overlay.py",
        "--output-root",
        str(tmp_path / "overlay-build"),
    )
    _run(
        "arda_os/distribution/scripts/render_distribution_manifest.py",
        "--manifest-output",
        str(tmp_path / "distribution-manifest.json"),
        "--installer-profile-output",
        str(tmp_path / "installer-profile.json"),
    )
    _run(
        "arda_os/distribution/scripts/render_rootfs_plan.py",
        "--output",
        str(tmp_path / "rootfs-plan.json"),
    )
    _run(
        "arda_os/distribution/scripts/assemble_image_workspace.py",
        "--rootfs-plan",
        str(tmp_path / "rootfs-plan.json"),
        "--overlay-root",
        str(Path(overlay_output["overlay_root"])),
        "--distribution-manifest",
        str(tmp_path / "distribution-manifest.json"),
        "--workspace-root",
        str(tmp_path / "workspace"),
    )
    _run(
        "arda_os/distribution/scripts/render_image_artifact_plan.py",
        "--rootfs-plan",
        str(tmp_path / "rootfs-plan.json"),
        "--output",
        str(tmp_path / "image-artifact-plan.json"),
    )
    _run(
        "arda_os/distribution/scripts/assemble_artifact_workspace.py",
        "--image-plan",
        str(tmp_path / "image-artifact-plan.json"),
        "--workspace-summary",
        str(tmp_path / "workspace" / "plans" / "workspace-summary.json"),
        "--output-root",
        str(tmp_path / "artifact-workspace"),
    )
    payload = _run(
        "arda_os/distribution/scripts/export_artifact_workspace_shell.py",
        "--summary",
        str(tmp_path / "artifact-workspace" / "plans" / "artifact-workspace-summary.json"),
        "--output",
        str(tmp_path / "run-artifact-workspace.sh"),
    )

    assert payload["ok"] is True
    script = (tmp_path / "run-artifact-workspace.sh").read_text(encoding="utf-8")
    assert "emit_raw_disk" in script
    assert "xorriso" in script
    assert "mkfs.vfat" in script
    assert "-append_partition" in script


def test_run_artifact_workspace_dry_run_reports_emission_steps(tmp_path):
    overlay_output = _run(
        "arda_os/distribution/scripts/prepare_arda_overlay.py",
        "--output-root",
        str(tmp_path / "overlay-build"),
    )
    _run(
        "arda_os/distribution/scripts/render_distribution_manifest.py",
        "--manifest-output",
        str(tmp_path / "distribution-manifest.json"),
        "--installer-profile-output",
        str(tmp_path / "installer-profile.json"),
    )
    _run(
        "arda_os/distribution/scripts/render_rootfs_plan.py",
        "--output",
        str(tmp_path / "rootfs-plan.json"),
    )
    _run(
        "arda_os/distribution/scripts/assemble_image_workspace.py",
        "--rootfs-plan",
        str(tmp_path / "rootfs-plan.json"),
        "--overlay-root",
        str(Path(overlay_output["overlay_root"])),
        "--distribution-manifest",
        str(tmp_path / "distribution-manifest.json"),
        "--workspace-root",
        str(tmp_path / "workspace"),
    )
    _run(
        "arda_os/distribution/scripts/render_image_artifact_plan.py",
        "--rootfs-plan",
        str(tmp_path / "rootfs-plan.json"),
        "--output",
        str(tmp_path / "image-artifact-plan.json"),
    )
    _run(
        "arda_os/distribution/scripts/assemble_artifact_workspace.py",
        "--image-plan",
        str(tmp_path / "image-artifact-plan.json"),
        "--workspace-summary",
        str(tmp_path / "workspace" / "plans" / "workspace-summary.json"),
        "--output-root",
        str(tmp_path / "artifact-workspace"),
    )
    payload = _run(
        "arda_os/distribution/scripts/run_artifact_workspace.py",
        "--summary",
        str(tmp_path / "artifact-workspace" / "plans" / "artifact-workspace-summary.json"),
        "--output",
        str(tmp_path / "artifact-workspace-run-report.json"),
    )

    assert payload["execute"] is False
    assert payload["selected_order"][0] == "pack_rootfs"
    assert "make_live_rootfs" in payload["selected_order"]
    assert payload["steps"]


def test_run_artifact_workspace_execute_refuses_empty_rootfs_snapshot(tmp_path):
    overlay_output = _run(
        "arda_os/distribution/scripts/prepare_arda_overlay.py",
        "--output-root",
        str(tmp_path / "overlay-build"),
    )
    _run(
        "arda_os/distribution/scripts/render_distribution_manifest.py",
        "--manifest-output",
        str(tmp_path / "distribution-manifest.json"),
        "--installer-profile-output",
        str(tmp_path / "installer-profile.json"),
    )
    _run(
        "arda_os/distribution/scripts/render_rootfs_plan.py",
        "--output",
        str(tmp_path / "rootfs-plan.json"),
    )
    _run(
        "arda_os/distribution/scripts/assemble_image_workspace.py",
        "--rootfs-plan",
        str(tmp_path / "rootfs-plan.json"),
        "--overlay-root",
        str(Path(overlay_output["overlay_root"])),
        "--distribution-manifest",
        str(tmp_path / "distribution-manifest.json"),
        "--workspace-root",
        str(tmp_path / "workspace"),
    )
    _run(
        "arda_os/distribution/scripts/render_image_artifact_plan.py",
        "--rootfs-plan",
        str(tmp_path / "rootfs-plan.json"),
        "--output",
        str(tmp_path / "image-artifact-plan.json"),
    )
    _run(
        "arda_os/distribution/scripts/assemble_artifact_workspace.py",
        "--image-plan",
        str(tmp_path / "image-artifact-plan.json"),
        "--workspace-summary",
        str(tmp_path / "workspace" / "plans" / "workspace-summary.json"),
        "--output-root",
        str(tmp_path / "artifact-workspace"),
    )
    completed = _run_raw(
        "arda_os/distribution/scripts/run_artifact_workspace.py",
        "--summary",
        str(tmp_path / "artifact-workspace" / "plans" / "artifact-workspace-summary.json"),
        "--output",
        str(tmp_path / "artifact-workspace-run-report.json"),
        "--execute",
    )
    assert completed.returncode == 1
    payload = json.loads(completed.stdout)

    assert payload["execute"] is True
    assert payload["ok"] is False
    assert "rootfs_snapshot_empty" in payload["blockers"]
    assert payload["steps"] == []


def test_run_artifact_workspace_execute_fails_when_output_is_missing(tmp_path):
    summary = {
        "artifact_workspace_root": str(tmp_path / "artifact-workspace"),
        "build_commands": {
            "emit_live_iso": [
                "python3",
                "-c",
                "print('no iso emitted')",
                str(tmp_path / "artifact-workspace" / "release" / "missing.iso"),
            ]
        },
        "blockers": [],
    }
    summary_path = tmp_path / "artifact-workspace" / "plans" / "artifact-workspace-summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    output_path = tmp_path / "artifact-workspace-run-report.json"

    completed = _run_raw(
        "arda_os/distribution/scripts/run_artifact_workspace.py",
        "--summary",
        str(summary_path),
        "--output",
        str(output_path),
        "--execute",
        "--start-at",
        "emit_live_iso",
        "--stop-after",
        "emit_live_iso",
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert payload["steps"][0]["ok"] is False
    assert "expected_output_missing" in payload["steps"][0]["stderr"]

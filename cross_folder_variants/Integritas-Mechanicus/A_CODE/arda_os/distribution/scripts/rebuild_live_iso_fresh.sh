#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

PYTHON="${PYTHON:-./.venv/bin/python3}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

WORKSPACE="arda_os/distribution/build/workspace"
ARTIFACT_WORKSPACE="arda_os/distribution/build/artifact-workspace"
LOG_DIR="arda_os/distribution/build/logs"

mkdir -p "$LOG_DIR"

echo "ARDA_REBUILD: rendering rootfs plan"
"$PYTHON" arda_os/distribution/scripts/render_rootfs_plan.py \
  --output arda_os/distribution/build/rootfs-plan.json

echo "ARDA_REBUILD: preparing fresh overlay"
"$PYTHON" arda_os/distribution/scripts/prepare_arda_overlay.py \
  --output-root arda_os/distribution/build/overlay >"$LOG_DIR/arda-prepare-overlay.json"

echo "ARDA_REBUILD: removing stale build workspaces"
sudo rm -rf "$WORKSPACE" "$ARTIFACT_WORKSPACE"

echo "ARDA_REBUILD: assembling image workspace from fresh overlay"
"$PYTHON" arda_os/distribution/scripts/assemble_image_workspace.py \
  --rootfs-plan arda_os/distribution/build/rootfs-plan.json \
  --overlay-root arda_os/distribution/build/overlay/rootfs \
  --distribution-manifest arda_os/distribution/releases/distribution-manifest.json \
  --workspace-root "$WORKSPACE" \
  | tee arda_os/distribution/build/workspace-assemble-report.json

echo "ARDA_REBUILD: building rootfs"
sudo "$PYTHON" arda_os/distribution/scripts/run_image_workspace.py \
  --summary "$WORKSPACE/plans/workspace-summary.json" \
  --output "$WORKSPACE/plans/workspace-fresh-run-report.json" \
  --execute

echo "ARDA_REBUILD: rendering artifact plan"
"$PYTHON" arda_os/distribution/scripts/render_image_artifact_plan.py \
  --rootfs-plan arda_os/distribution/build/rootfs-plan.json \
  --output arda_os/distribution/build/image-artifact-plan.json

echo "ARDA_REBUILD: assembling artifact workspace"
sudo env ARDA_VM_SNAKEOIL_SECURE_BOOT=1 "$PYTHON" arda_os/distribution/scripts/assemble_artifact_workspace.py \
  --image-plan arda_os/distribution/build/image-artifact-plan.json \
  --workspace-summary "$WORKSPACE/plans/workspace-summary.json" \
  --output-root "$ARTIFACT_WORKSPACE" \
  | tee arda_os/distribution/build/artifact-workspace-assemble-report.json

echo "ARDA_REBUILD: emitting live ISO"
sudo env ARDA_VM_SNAKEOIL_SECURE_BOOT=1 "$PYTHON" arda_os/distribution/scripts/run_artifact_workspace.py \
  --summary "$ARTIFACT_WORKSPACE/plans/artifact-workspace-summary.json" \
  --output "$ARTIFACT_WORKSPACE/plans/artifact-fresh-run-report.json" \
  --execute \
  --start-at make_live_rootfs \
  --stop-after emit_live_iso

ISO="$ARTIFACT_WORKSPACE/release/arda-valinor-live-trixie-amd64.iso"
SQUASH="$ARTIFACT_WORKSPACE/boot-staging/live/filesystem.squashfs"

echo "ARDA_REBUILD: verifying baked desktop probe"
unsquashfs -ll "$SQUASH" usr/local/bin/arda-wallpaper-probe
unsquashfs -ll "$SQUASH" usr/local/bin/arda-live-desktop-awakening
unsquashfs -ll "$SQUASH" etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml
unsquashfs -ll "$SQUASH" usr/share/backgrounds/xfce/xfce-teal.svg
unsquashfs -ll "$SQUASH" usr/share/plymouth/themes/arda-mirror-gate/arda-mirror-gate.plymouth
unsquashfs -ll "$SQUASH" etc/plymouth/plymouthd.conf

echo "ARDA_REBUILD: done"
ls -lh "$ISO"

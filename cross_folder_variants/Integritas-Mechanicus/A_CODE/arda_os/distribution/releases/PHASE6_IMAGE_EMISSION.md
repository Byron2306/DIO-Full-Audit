# Phase 6: Image Emission

This phase converts the staged ARDA distribution workspace into actual releasable
artifacts:

- raw disk image
- live ISO
- installer ISO

## Inputs

- `arda_os/distribution/build/workspace/plans/workspace-summary.json`
- `arda_os/distribution/releases/image-artifact-plan.json`
- staged Valinor kernel `.deb` artifacts
- generated ARDA overlay

## Workspace products

`assemble_artifact_workspace.py` produces:

- `rootfs-snapshot/`
- `overlay-snapshot/`
- `esp/`
- `boot-staging/`
- `release/`
- `plans/artifact-workspace-summary.json`

## Host execution model

`export_artifact_workspace_shell.py` emits a shell runner that performs:

1. rootfs tarball creation
2. EFI system partition image sizing
3. raw disk image allocation
4. live ISO emission
5. installer ISO emission

The generated shell script is designed to be the handoff point for privileged
host execution or CI runners that have the required image-building tools.

`run_artifact_workspace.py` provides the non-destructive readiness gate for this
phase by checking whether the required host tools and emission commands are
available before attempting a real build.

Actual image emission also requires a populated rootfs workspace from the prior
distribution build stage. If `rootfs_snapshot_empty` is reported, run the
rootfs/image workspace execution lane first so `debootstrap`, package install,
overlay application, and kernel staging have produced a real root filesystem.

# ARDA Distribution

This directory is the beginning of the ARDA OS distribution layer.

It sits above the current:

- Valinor kernel build and release flow
- host integration scripts
- boot theme and desktop identity assets
- policy and attestation runtime

The goal is to move from "hardened host substrate" to "installable ARDA distribution".

## Current phase

Phase 1 produces a reproducible distribution overlay and release plan.
Phase 2 produces a concrete rootfs assembly path for Debian-based ARDA images.
Phase 3 produces a staged image workspace with overlay and kernel artifacts.
Phase 4 produces executable workspace runners for dry-run and host execution.
Phase 5 produces concrete disk-image, live ISO, installer ISO, and release-bundle metadata.
Phase 6 produces the artifact-emission workspace and host shell runner for actual image output.
Phase 7 is the operationalization layer: host prerequisites, off-box verifier inputs, approved PCR baseline export, and release receipts that make the image path auditable.

It does not yet emit a bootable ISO by itself. Instead, it gives us:

- a generated root filesystem overlay
- a distribution manifest describing what must ship
- an installer profile describing required packages and services
- a concrete plan for converting a Debian base image into an ARDA image
- the scaffolding for release evidence that should ship with that image
- explicit off-box verifier deployment and attested-host client profiles

## Main entrypoints

- `scripts/prepare_arda_overlay.py`
  Builds a rootfs overlay tree under `build/overlay/`.

- `scripts/render_distribution_manifest.py`
  Emits a machine-readable distribution manifest and installer profile.

- `scripts/render_iso_plan.py`
  Emits the exact phased plan for producing an installer ISO from the current baseline.

- `scripts/render_rootfs_plan.py`
  Emits a concrete rootfs construction plan for `debootstrap` and `live-build`.

- `scripts/render_image_artifact_plan.py`
  Emits the concrete image-layout and artifact-emission plan for raw disk images and ISOs.

- `scripts/render_installer_recipe.py`
  Emits the installer recipe describing partitions, required units, and first-boot contract.

- `scripts/render_release_bundle.py`
  Emits the release bundle manifest tying the distribution, installer, and artifact plans together.

- `scripts/assemble_artifact_workspace.py`
  Produces the image-emission workspace with rootfs snapshot, release targets, and artifact build commands.

- `scripts/export_artifact_workspace_shell.py`
  Emits the shell runner for raw disk and ISO artifact emission.

- `scripts/run_artifact_workspace.py`
  Dry-runs or executes the artifact-emission commands so host build readiness is visible before privileged execution.
  It will refuse real artifact emission if the upstream rootfs workspace has not been populated yet.

- `scripts/boot_live_qemu_vtpm.py`
  Boots the emitted live ISO under OVMF with a persistent software TPM. Use
  the default UEFI/vTPM lane for repeatable PCR evidence, or add
  `--secure-boot` to test the stricter Secure Boot/vTPM path.

- `scripts/apply_overlay.py`
  Applies the generated ARDA overlay onto a prepared rootfs tree.

- `scripts/assemble_image_workspace.py`
  Produces a build workspace with rootfs target, staged overlay, staged kernel artifacts, and executable build commands.

- `scripts/run_image_workspace.py`
  Dry-runs or executes the workspace build pipeline in ordered steps.

- `scripts/export_image_workspace_shell.py`
  Emits a shell script version of the workspace build sequence for manual or CI execution.

## Output layout

Generated outputs live under:

- `arda_os/distribution/build/overlay/`
- `arda_os/distribution/build/rootfs-plan.json`
- `arda_os/distribution/releases/`

Key release outputs now include:

- `arda_os/distribution/releases/image-artifact-plan.json`
- `arda_os/distribution/releases/installer-recipe.json`
- `arda_os/distribution/releases/remote-verifier-profile.json`
- `arda_os/distribution/releases/release-bundle.json`
- `arda_os/distribution/releases/PHASE6_IMAGE_EMISSION.md`

## Near-term path to a real installer ISO

1. Build Valinor kernel artifacts.
2. Generate the ARDA overlay from this repo.
3. Apply the overlay to a Debian live-build or debootstrap rootfs.
4. Install the Valinor kernel, ARDA services, verifier config, policy artifacts, and identity assets.
5. Produce:
   - a live ISO
   - an installer ISO
   - a raw disk image for direct flashing
6. Ship a release bundle that captures the boot contract, installer contract, and produced artifact set.

## Production packaging additions now required

The distribution path should now also ship:

- the verifier public key used for signed rollout verdict verification
- the off-box verifier deployment profile and client env template
- a baseline PCR manifest for approved hardware/boot lanes
- post-boot attestation defaults so fresh proof is minted on first boot
- denial-proof receipt tooling for release validation and regression testing

## Virtualized sovereignty validation

The live image can be tested with a persistent QEMU TPM before installing it
onto hardware:

```bash
python3 arda_os/distribution/scripts/boot_live_qemu_vtpm.py
```

For the stricter lane, use Secure Boot OVMF variables:

```bash
python3 arda_os/distribution/scripts/boot_live_qemu_vtpm.py --secure-boot
```

The Secure Boot lane is expected to surface signing or MOK enrollment gaps
instead of hiding them. A passing vTPM lane proves the image can produce
virtual TPM evidence; a passing Secure Boot/vTPM lane is the closer rehearsal
for the installed hardware-rooted ARDA path.

## Design stance

The distribution should preserve the current proven baseline:

- Secure Boot visible and enabled
- TPM-backed attestation
- verifier-signed rollout control
- measured identity activation
- fail-closed recovery lanes

This layer exists to package those guarantees into something that can be installed on new hardware, not to replace them with a cosmetic rebrand.

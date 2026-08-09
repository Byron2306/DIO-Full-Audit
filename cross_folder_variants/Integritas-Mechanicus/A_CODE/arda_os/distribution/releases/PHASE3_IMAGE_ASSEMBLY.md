# ARDA Distribution Phase 3

Phase 3 introduces the first concrete image assembly workspace.

The generated workspace contains:

- `rootfs/`
  Target Debian root filesystem location.
- `overlay-rootfs/`
  A staged copy of the ARDA overlay.
- `artifacts/`
  Valinor kernel `.deb` artifacts copied into the workspace.
  Debug kernel packages are excluded by default to keep the workspace buildable on normal local storage.
- `plans/workspace-summary.json`
  Exact commands and paths required to assemble the image.

This phase still stops short of running:

- `debootstrap`
- `apt-get install` inside chroot
- `dpkg -i` for kernel packages inside the rootfs
- ISO emission

Those are the next build-execution boundary.

## Typical sequence

1. Generate overlay.
2. Render distribution manifest.
3. Render rootfs plan.
4. Assemble image workspace.
5. Execute rootfs commands on a build host with required privileges and network access.

# Valinor Phase 3 Guardrails

Phase 3 begins only after `.deb` kernel packages exist. It must remain
rollback-safe until a Valinor kernel has booted and passed the post-boot gate.

## Required Sequence

1. Generate a release manifest for the package output directory.
2. Verify every artifact hash in that manifest.
3. Generate a non-mutating install plan.
4. Run the preinstall gate against the manifest and install plan.
5. Read the install plan before running any `dpkg -i` command.
6. Install packages only when the plan contains both a `linux-image` and
   matching `linux-headers` package.
7. Render and review Valinor systemd units before enabling them.
8. Reboot manually and select the Valinor kernel entry.
9. Run the post-boot gate.
10. Only then run ARDA promotion gates on the booted Valinor kernel.

## Commands

```bash
arda_os/kernel/valinor/scripts/release_manifest.py \
  --source-dir ~/kernel-src/linux-source-6.12 \
  --artifact-dir ~/kernel-src \
  --output arda_os/kernel/valinor/releases/latest.json

arda_os/kernel/valinor/scripts/verify_release_manifest.py \
  --manifest arda_os/kernel/valinor/releases/latest.json

arda_os/kernel/valinor/scripts/plan_valinor_install.py \
  --manifest arda_os/kernel/valinor/releases/latest.json \
  --output arda_os/kernel/valinor/releases/install-plan.latest.json

arda_os/kernel/valinor/scripts/preinstall_valinor_gate.py \
  --manifest arda_os/kernel/valinor/releases/latest.json \
  --install-plan arda_os/kernel/valinor/releases/install-plan.latest.json

arda_os/kernel/valinor/scripts/render_systemd_units.py \
  --output-dir arda_os/kernel/valinor/releases/systemd

arda_os/kernel/valinor/scripts/post_boot_valinor_gate.py
```

## Current Expected Gate Behavior

On the current Debian RT kernel, `post_boot_valinor_gate.py` should fail with:

```text
valinor_kernel
```

That is correct. The gate must not pass until `uname -r` contains `valinor`.

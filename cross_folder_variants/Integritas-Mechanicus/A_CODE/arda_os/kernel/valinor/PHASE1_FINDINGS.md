# Valinor Phase 1 Findings

Captured host kernel:

```text
6.12.95+deb13-rt-amd64
```

Baseline config:

```text
arda_os/kernel/valinor/config.base
```

## Config Contract Result

The running Debian RT kernel already satisfies the majority of the Valinor
feature contract:

- BPF, BPF syscall, BPF JIT, and BPF LSM are enabled.
- BTF debug info is enabled.
- securityfs and lockdown LSM are enabled.
- EFI support is enabled.
- fs-verity and built-in fs-verity signatures are enabled.
- IMA and EVM are enabled.
- TPM, TIS, and CRB support are enabled.
- audit and audit syscall support are enabled.

Current blockers against `config.fragment`:

```text
CONFIG_LSM
CONFIG_EFIVAR_FS
CONFIG_EFI_VARS_PSTORE
```

## Interpretation

`CONFIG_EFIVAR_FS=m` and `CONFIG_EFI_VARS_PSTORE=m` are likely contributors to
the current Secure Boot visibility problem only if the modules are absent,
unloaded, or blocked by the boot/runtime environment. Valinor requires them
built in so EFI variable visibility is available during early boot and does not
depend on late module loading.

`CONFIG_LSM` differs from the desired Valinor ordering. The current kernel does
include `bpf` in the active LSM chain, but Valinor should carry an explicit,
audited LSM ordering so ARDA enforcement is not an accident of host defaults.

## Phase 1 Exit Criteria

Phase 1 is complete when:

- the Valinor workspace exists,
- the running kernel config has been captured,
- the required feature contract is documented,
- the checker identifies blockers reproducibly,
- the build wrapper can be pointed at a Linux source tree without mutating boot
  entries,
- the release manifest script can hash produced packages.

Phase 2 begins when a Linux source tree is selected and `.config` is prepared
from `config.base` plus the Valinor fragment.

The Phase 2 preparation command is:

```bash
arda_os/kernel/valinor/scripts/prepare_valinor_config.py --source-dir /path/to/linux-source
```

## Phase 1 Live Kernel Update

As of the workstation Valinor boot, the live kernel target is:

```text
6.12.96-valinor
```

The corrected workstation kernel package contains Intel graphics support:

```text
/lib/modules/6.12.96-valinor/kernel/drivers/gpu/drm/i915/i915.ko.xz
```

The first broken RT-flavored build remains identifiable as:

```text
6.12.96-valinor-valinor
```

Do not remove fallback kernels until a second clean boot into
`6.12.96-valinor` passes `valinor_health_report.py`.

Current Phase 1 live-health command:

```bash
arda_os/kernel/valinor/scripts/valinor_health_report.py --json
```

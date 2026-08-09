# Valinor Phase 2 Findings

Phase 2 begins the reproducible kernel source preparation path. This phase is
still non-mutating: it prepares a Linux source tree `.config`, but does not
build, install, sign, or select a boot entry by itself.

## Added Tooling

- `scripts/prepare_valinor_config.py`
  Copies `config.base` into a Linux source tree, applies `config.fragment`, runs
  `make olddefconfig`, and validates the result with the Valinor config checker.

- `scripts/build_valinor_kernel.sh`
  Now refuses to build unless `.config` satisfies `config.fragment`, unless
  explicitly run with `--skip-config-check`.

## Smoke Test

A temporary Makefile-based source stand-in was used to validate the config
preparation logic without requiring a full Linux checkout. The tool:

- copied `config.base`,
- applied all 21 required Valinor config values,
- ran the fake `olddefconfig` target,
- passed `check_valinor_config.py` with zero blockers.

## Phase 2 Exit Criteria

Phase 2 is complete when the same preparation command succeeds against a real
Linux source tree:

```bash
arda_os/kernel/valinor/scripts/prepare_valinor_config.py --source-dir /path/to/linux-source
```

Then the first non-installed package build can be attempted:

```bash
arda_os/kernel/valinor/scripts/build_valinor_kernel.sh \
  --source-dir /path/to/linux-source \
  --jobs "$(nproc)"
```

No boot entries should be changed until a release manifest exists and package
hashes are recorded.

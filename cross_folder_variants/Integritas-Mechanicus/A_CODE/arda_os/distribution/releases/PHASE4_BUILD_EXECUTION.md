# ARDA Distribution Phase 4

Phase 4 introduces build execution tooling for the assembled image workspace.

This phase adds:

- a dry-run and execution runner for workspace commands
- a shell export for CI or manual host execution

## New entrypoints

- `arda_os/distribution/scripts/run_image_workspace.py`
- `arda_os/distribution/scripts/export_image_workspace_shell.py`

## Recommended workflow

1. Generate overlay.
2. Render distribution manifest.
3. Render rootfs plan.
4. Assemble image workspace.
5. Dry-run the workspace:
   - `run_image_workspace.py`
6. Export the shell script if desired.
7. Execute on a privileged build host with:
   - `debootstrap`
   - network access
   - chroot capability
   - package installation rights

## Notes

The repo now contains the orchestration needed for rootfs execution, but it does not yet force execution in this environment. That remains the correct boundary because image building needs elevated system access and Debian package/bootstrap tooling.

Dry-run mode exits successfully even when required host tools such as `debootstrap` are not installed yet. The missing commands are recorded in the run report instead of being treated as a script failure.
